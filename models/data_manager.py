from .bookcover_manager import BookCoverManager
from pathlib import Path
import pandas as pd
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

    book_df["title_pron"] = book_df["title"].map(lambda x:x["@pronunciation"])
    book_df["title"] = book_df["title"].map(lambda x:x["#text"])

    book_df["authors"] = book_df["authors"].map(lambda x_list:",".join([x["#text"] for x in x_list]))
    book_df["publishers"] = book_df["publishers"].str.join(',')

    book_df["origin_type"] = book_df["origins"].map(lambda x:x["origin"]['type'])
    book_df.drop(["origins"],axis=1,inplace=True)

    # 無料という文字列が入った書籍は削除
    book_df = book_df[~book_df["title"].str.contains("無料")]
    
    # 購入日が欠損の本は最初から入っている辞書？等で不要なので削除
    book_df.dropna(subset=["purchase_date"],inplace=True)

    book_df["publication_date"] = pd.to_datetime(book_df["publication_date"]).dt.tz_localize(None)
    book_df["purchase_date"] = pd.to_datetime(book_df["purchase_date"]).dt.tz_convert('Asia/Tokyo').dt.tz_localize(None)
    
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

class DataManager():
    def __init__(self,metadata_path,shelf_info_path,bookcovers_path):
        self.metadata_path   = Path(metadata_path)
        self.shelf_info_path = Path(shelf_info_path)
        self.bcover_manager = BookCoverManager(metadata_path,bookcovers_path)

        if(not self.shelf_info_path.exists()):
            self.shelf_info_path.mkdir()

        if(not (self.shelf_info_path/"book_info.json").exists()):
            self.init_book_db()
    
    def init_book_db(self):
        book_df = read_kindle_metadata(self.metadata_path)
        with open(self.shelf_info_path/'book_info.json', 'w', encoding='utf-8') as f:
            book_df.to_json(f,orient="records",force_ascii=False,indent=4)
            
        series_df = pd.DataFrame(columns=["series_id","rating","tags"])
        series_df["series_id"] = book_df["series_id"].unique()
        with open(self.shelf_info_path/'series_info.json', 'w', encoding='utf-8') as f:
            series_df.to_json(f,orient="records",force_ascii=False,indent=4)
        
        self.bcover_manager.add_bookcovers(book_df)

    def update_from_kindle(self):
        latest_book_df = read_kindle_metadata(self.metadata_path)
        
        # series_idのみユーザによる編集があるため現在の情報を保持
        current_book_df = pd.read_json(self.shelf_info_path/"book_info.json",orient="records").set_index("ASIN")
        latest_book_df.set_index("ASIN",inplace=True)
        common_index = latest_book_df[latest_book_df.index.isin(current_book_df.index)].index
        latest_book_df.loc[common_index,"series_id"] = current_book_df.loc[common_index,"series_id"]
        latest_book_df.reset_index(inplace=True)
        with open(self.shelf_info_path/'book_info.json', 'w', encoding='utf-8') as f:
            latest_book_df.to_json(f,orient="records",force_ascii=False,indent=4)

        current_series_df = pd.read_json(self.shelf_info_path/"series_info.json",orient="records").set_index("series_id")
        latest_series_set = set(latest_book_df["series_id"])
        additional_series_df = pd.DataFrame(index=latest_series_set-set(current_series_df.index),
                                            columns=current_series_df.columns)
        latest_series_df = pd.concat([current_series_df,additional_series_df])
        latest_series_df.index.name = "series_id"
        latest_series_df.reset_index(inplace=True)
        with open(self.shelf_info_path/'series_info.json', 'w', encoding='utf-8') as f:
            latest_series_df.to_json(f,orient="records",force_ascii=False,indent=4)            
            
        self.bcover_manager.add_bookcovers(latest_book_df)