from .bookcover_manager import BookCoverManager
from pathlib import Path
import pandas as pd
import sqlite3
import re

import numpy as np

import plistlib
from typing import Any, Dict

def resolve_ns_keyed_archive_fully(data: bytes) -> Any:
    if pd.isna(data):
        return np.nan
    root = plistlib.loads(data)
    objects = root["$objects"]
    top_uid = root["$top"]["root"]

    # クラスID → クラス名
    class_map = {
        idx: obj["$classname"]
        for idx, obj in enumerate(objects)
        if isinstance(obj, dict) and "$classname" in obj
    }

    def resolve(obj: Any, memo: Dict[int, Any]) -> Any:
        if isinstance(obj, plistlib.UID):
            idx = obj.data
            if idx in memo:
                return memo[idx]
            raw = objects[idx]
            resolved = resolve(raw, memo)
            memo[idx] = resolved
            return resolved

        elif isinstance(obj, list):
            return [resolve(item, memo) for item in obj]

        elif isinstance(obj, dict):
            # クラスID に基づいて判定
            class_id = obj.get("$class")
            class_name = class_map.get(class_id.data) if isinstance(class_id, plistlib.UID) else None

            # NSMutableArray / NSArray の展開
            if class_name in ("NSMutableArray", "NSArray") and "NS.objects" in obj:
                return resolve(obj["NS.objects"], memo)

            # NSMutableDictionary / NSDictionary の展開
            if class_name in ("NSMutableDictionary", "NSDictionary") and "NS.keys" in obj and "NS.objects" in obj:
                keys = resolve(obj["NS.keys"], memo)
                vals = resolve(obj["NS.objects"], memo)
                return dict(zip(keys, vals))

            # 通常の辞書展開
            return {
                resolve(k, memo): resolve(v, memo)
                for k, v in obj.items()
                if not (isinstance(k, str) and k.startswith("$"))
            }

        else:
            return obj

    return resolve(top_uid, {})
    
def get_author(x):
    if not isinstance(x, dict):
        return np.nan
    attributes = x.get("attributes")
    if not isinstance(attributes, dict):
        return np.nan
    authors = attributes.get("authors")
    if not isinstance(authors, dict):
        return np.nan
    author = authors.get("author")
    if author is None:
        return np.nan
    if isinstance(author, list):  # 複数人の場合リスト
        return "/".join(author)
    return author  # 一人の場合単なる文字列

def get_origin_type(x):
    if not isinstance(x, dict):
        return np.nan
    attributes = x.get("attributes")
    if not isinstance(attributes, dict):
        return np.nan
    origins = attributes.get("origins")
    if not isinstance(origins, dict):
        return np.nan
    origin = origins.get("origin")
    if not isinstance(origin, dict):
        return np.nan
    type_value = origin.get("type")
    if type_value is None:
        return np.nan
    return type_value

def get_date(x,key):
    if not isinstance(x, dict):
        return np.nan
    attributes = x.get("attributes")
    if not isinstance(attributes, dict):
        return np.nan
    date = attributes.get(key)
    return date

def read_kindle_metadata(metadata_path):
    conn = sqlite3.connect(Path(metadata_path)/"Protected/BookData.sqlite")
    book_df = pd.read_sql_query('SELECT * FROM ZBOOK', conn)
    groupitem_df = pd.read_sql_query('SELECT * FROM ZGROUPITEM', conn)
    group_df = pd.read_sql_query('SELECT * FROM ZGROUP', conn)

    book_df["ASIN"]=book_df["ZBOOKID"].map(lambda x:x.split(":")[1].split("-")[0])
    book_df["ZSYNCMETADATAATTRIBUTES"] = book_df["ZSYNCMETADATAATTRIBUTES"].map(resolve_ns_keyed_archive_fully)

    groupitem_df = pd.merge(
        groupitem_df.drop(["Z_PK","Z_ENT","Z_OPT"],axis=1),
        group_df.drop(["Z_ENT","Z_OPT"],axis=1),
        how='left',
        left_on='ZPARENTCONTAINER',
        right_on='Z_PK'
    ) 
    book_df = pd.merge(
        book_df.drop(["ZGROUPID"],axis=1), # こっちのZGROUPIDは空
        groupitem_df[["ZBOOK","ZGROUPID","ZPOSITIONLABEL"]],
        how='left',
        left_on='Z_PK',
        right_on='ZBOOK'
    )
    book_df["series_id"]=book_df["ZGROUPID"]
    book_df["series_num"]=book_df["ZPOSITIONLABEL"]

    series_df = pd.DataFrame(index=group_df.index)
    series_df["series_id"]=group_df["ZGROUPID"]
    series_df["series_pron"]=group_df["ZSORTTITLE"]
    series_df["first_title"]=group_df["ZDISPLAYNAME"]    

    book_df["origin_type"] = book_df["ZSYNCMETADATAATTRIBUTES"].map(get_origin_type)

    book_df["title_pron"] = book_df["ZSORTTITLE"]
    book_df["title"] = book_df["ZDISPLAYTITLE"]

    # book_df["authors_pron"] = ???
    book_df["authors"] = book_df["ZSYNCMETADATAATTRIBUTES"].map(get_author)
    book_df["publishers"] = book_df["ZRAWPUBLISHER"]
    

    # 無料という文字列が入った書籍は削除。例：【期間限定無料】
    book_df = book_df[~book_df["title"].fillna("").str.contains("無料")]

    book_df = book_df[book_df["origin_type"]!="Sample"] # 書籍サンプルを除外
    book_df = book_df[book_df["origin_type"]!="KindleDictionary"] # デフォルトで入っている辞書を除外
    
    # kindleに最初から入っている辞書でpronunciationが空になることを確認。英書籍だとそうなると仮定しtitleで埋める
    book_df.loc[book_df["title_pron"]=="","title_pron"]=book_df.loc[book_df["title_pron"]=="","title"]
    # book_df.loc[book_df["authors_pron"]=="","authors_pron"]=book_df.loc[book_df["authors_pron"]=="","authors"]

    # datetime型に変換
    book_df["publication_date"] = book_df["ZSYNCMETADATAATTRIBUTES"].map(lambda x:get_date(x,"publication_date"))
    book_df["purchase_date"] = book_df["ZSYNCMETADATAATTRIBUTES"].map(lambda x:get_date(x,"purchase_date"))
    book_df["publication_date"] = pd.to_datetime(book_df["publication_date"])
    book_df["purchase_date"] = pd.to_datetime(book_df["purchase_date"])
    # int64型に変換する際に欠損は扱えないため埋めるか消す
    book_df["publication_date"] = book_df["publication_date"] .fillna(pd.to_datetime("2200-01-01")) # たまに欠損が存在する
    book_df = book_df.dropna(subset=["purchase_date"]) # kindleにデフォルトで入っている辞典は購入日欠損。不要なので除外

    book_df.loc[book_df["series_id"].isna(),"series_id"]=book_df.loc[book_df["series_id"].isna(),"ASIN"]
    book_df["series_count"] = book_df.groupby("series_id").transform("size")
    
    # Kindle Unlimited購入と実購入で同じ本が入る場合があるため、重複を削除
    book_df.drop_duplicates(subset=["ASIN"],inplace=True) 
    
    return book_df,series_df

def read_kindle_collection(metadata_path,book_df):
    collection_path = metadata_path/"db/synced_collections.db"
    conn = sqlite3.connect(collection_path)
    collections_df = pd.read_sql_query('SELECT * FROM cloud_collections', conn)
    collections_items_df = pd.read_sql_query('SELECT * FROM cloud_collections_items', conn)
    # コレクションIDと名前の紐づけ
    clctn_df = (pd.merge(collections_items_df,
                        collections_df[["id","name"]].rename(columns={"name":"collection_name"}),
                        left_on='collection_id',
                        right_on='id')
                .drop(['id'],axis=1))

    # 書籍名とASINの紐づけ
    clctn_df = (pd.merge(clctn_df,
                        book_df,#[["ASIN","title"]],
                        left_on='book_asin',
                        right_on='ASIN')
                .drop(['book_asin'],axis=1))
    # datetime型に変換
    clctn_df['last_updated_timestamp'] = (pd.to_datetime(clctn_df['last_updated_timestamp'])
                                        .dt.tz_convert('Asia/Tokyo').dt.tz_localize(None))
    return clctn_df

class DataManager():
    def __init__(self,metadata_path,shelf_info_path,bookcovers_path):
        self.metadata_path   = Path(metadata_path)
        self.shelf_info_path = Path(shelf_info_path)
        self.bcover_manager = BookCoverManager(metadata_path,bookcovers_path)

        if(not self.shelf_info_path.exists()):
            self.shelf_info_path.mkdir()

        if(not (self.shelf_info_path/"shelf_info.xlsx").exists()):
            self.init_book_db()
    
    def init_book_db(self):
        book_df,series_df = read_kindle_metadata(self.metadata_path)
        series_df["rating"] = pd.NA
        series_df["tags"] = pd.NA
        clctn_df = read_kindle_collection(self.metadata_path,book_df)

        with pd.ExcelWriter(self.shelf_info_path/'shelf_info.xlsx') as writer:
            book_df.to_excel(writer,index=False, sheet_name='book')
            series_df.to_excel(writer, index=False, sheet_name='series')
            clctn_df.to_excel(writer, index=False, sheet_name='collection')
        
        self.bcover_manager.add_bookcovers(book_df)

    def update_from_kindle(self):
        book_df,series_df = read_kindle_metadata(self.metadata_path)
        clctn_df = read_kindle_collection(self.metadata_path,book_df)

        prev_series_df = pd.read_excel(self.shelf_info_path/'shelf_info.xlsx',sheet_name='series')
        series_df = pd.merge(series_df,prev_series_df[["series_id","rating","tags"]],on='series_id',how='left')

        with pd.ExcelWriter(self.shelf_info_path/'shelf_info.xlsx') as writer:
            book_df.to_excel(writer,index=False, sheet_name='book')
            series_df.to_excel(writer, index=False, sheet_name='series')       
            clctn_df.to_excel(writer, index=False, sheet_name='collection') 
            
        self.bcover_manager.add_bookcovers(book_df)