from .bookcover_manager import BookCoverManager
from pathlib import Path
import pandas as pd
import sqlite3
import xmltodict
import re

def modify_metadata_dict(metadata_dict):
    # 一つの書籍に対して著者が、欠損か、１つだけか、複数あるかによってauthors要素内の型が変わる。
    # ・複数ある場合は、author辞書のリスト、
    # ・1つだけの場合は、author辞書、
    # ・欠損の場合は辞書でもリストでもない。
    # publishersも同様。
    # これを、1つの場合でも欠損の場合でもリストを持つように統一
    for md in metadata_dict["response"]["add_update_list"]["meta_data"]:
        if(not isinstance(md["authors"],dict)):  # 著者欠損の場合
            md["authors"] = {"author":[]}
        elif(not isinstance(md["authors"]["author"],list)):  # 著者が一人だけの場合
            md["authors"]["author"] = [md["authors"]["author"]]
        md["authors"] = md["authors"]["author"] # "authors":{"author":[{},{},{}]} →　"authors":[{},{},{}]

        if(not isinstance(md["publishers"],dict)):
            md["publishers"] = {"publisher":[]}
        elif(not isinstance(md["publishers"]["publisher"],list)):
            md["publishers"]["publisher"] = [md["publishers"]["publisher"]]
        md["publishers"] = md["publishers"]["publisher"]

def get_series_and_num(x):
    # 数字の前にスペースがある場合とない場合がある。連番2桁の場合と3桁の場合がある
    pattern = '([ァ-ヴ][ァ-ヴー・]+\s*)(\d+)' 
    rm = re.match(pattern,x)
    if(rm):
        return pd.Series([rm.group(1),int(rm.group(2))])
    else:
        return pd.Series([x,None])

def metadata_list2df(metadata_list):
    book_df = pd.DataFrame.from_dict(metadata_list)

    book_df["origin_type"] = book_df["origins"].map(lambda x:x["origin"]['type'])
    book_df.drop(["origins"],axis=1,inplace=True)

    book_df["title_pron"] = book_df["title"].map(lambda x:x["@pronunciation"])
    book_df["title"] = book_df["title"].map(lambda x:x["#text"])

    book_df["authors_pron"] = book_df["authors"].map(lambda x_list:"/".join([x["@pronunciation"] for x in x_list]))
    book_df["authors"] = book_df["authors"].map(lambda x_list:"/".join([x["#text"] for x in x_list]))
    book_df["publishers"] = book_df["publishers"].str.join('/')

    # 無料という文字列が入った書籍は削除。例：【期間限定無料】
    book_df = book_df[~book_df["title"].str.contains("無料")]

    book_df = book_df[book_df["origin_type"]!="Sample"] # 書籍サンプルを除外
    book_df[book_df["origin_type"]!="KindleDictionary"] # デフォルトで入っている辞書を除外
    
    # kindleに最初から入っている辞書でpronunciationが空になることを確認。英書籍だとそうなると仮定しtitleで埋める
    book_df.loc[book_df["title_pron"]=="","title_pron"]=book_df.loc[book_df["title_pron"]=="","title"]
    book_df.loc[book_df["authors_pron"]=="","authors_pron"]=book_df.loc[book_df["authors_pron"]=="","authors"]

    # datetime型に変換。publication_dateはUTCでpurchase_dateはJST。
    book_df["publication_date"] = pd.to_datetime(book_df["publication_date"]).dt.tz_localize(None)
    book_df["purchase_date"] = pd.to_datetime(book_df["purchase_date"]).dt.tz_convert('Asia/Tokyo').dt.tz_localize(None)
    # int64型に変換する際に欠損は扱えないため埋めるか消す
    book_df["publication_date"] = book_df["publication_date"] .fillna(pd.to_datetime("2200-01-01")) # たまに欠損が存在する
    book_df = book_df.dropna(subset=["purchase_date"]) # kindleにデフォルトで入っている辞典は購入日欠損。不要なので除外

    book_df[["series_pron","series_num"]] =  book_df["title_pron"].apply(get_series_and_num)
    book_df["series_num"] = book_df["series_num"].fillna(-1).astype(int)
    
    # Kindle Unlimited購入と実購入で同じ本が入る場合があるため、重複を削除
    book_df.drop_duplicates(subset=["ASIN"],inplace=True) 
    
    return book_df


def read_kindle_metadata(metadata_path):
    # kindle for PCのキャッシュファイルからメタデータ取得
    with open(Path(metadata_path)/"KindleSyncMetadataCache.xml", encoding='utf-8') as f:
        metadata_dict = xmltodict.parse(f.read())
    modify_metadata_dict(metadata_dict)
    
    metadata_list = metadata_dict["response"]["add_update_list"]["meta_data"]
    book_df = metadata_list2df(metadata_list)
    book_df["series_id"] = book_df["series_pron"].copy()
    return book_df

def get_series_df(book_df):
    series_df = (book_df
                .sort_values(["title_pron","series_num"])
                .groupby("series_id")
                .agg({"title":"first","series_num":"count"})
                .reset_index()
                .rename(columns={"title":"first_title","series_num":"series_count"}))
    return series_df

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
        book_df = read_kindle_metadata(self.metadata_path)
        series_df = get_series_df(book_df)
        series_df["rating"] = pd.NA
        series_df["tags"] = pd.NA
        clctn_df = read_kindle_collection(self.metadata_path,book_df)

        with pd.ExcelWriter(self.shelf_info_path/'shelf_info.xlsx') as writer:
            book_df.to_excel(writer,index=False, sheet_name='book')
            series_df.to_excel(writer, index=False, sheet_name='series')
            clctn_df.to_excel(writer, index=False, sheet_name='collection')
        
        self.bcover_manager.add_bookcovers(book_df)

    def update_from_kindle(self):
        book_df = read_kindle_metadata(self.metadata_path)
        series_df = get_series_df(book_df)
        clctn_df = read_kindle_collection(self.metadata_path,book_df)

        prev_series_df = pd.read_excel(self.shelf_info_path/'shelf_info.xlsx',sheet_name='series')
        series_df = pd.merge(series_df,prev_series_df[["series_id","rating","tags"]],on='series_id',how='left')

        with pd.ExcelWriter(self.shelf_info_path/'shelf_info.xlsx') as writer:
            book_df.to_excel(writer,index=False, sheet_name='book')
            series_df.to_excel(writer, index=False, sheet_name='series')       
            clctn_df.to_excel(writer, index=False, sheet_name='collection') 
            
        self.bcover_manager.add_bookcovers(book_df)