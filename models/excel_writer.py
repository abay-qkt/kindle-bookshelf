import pandas as pd
from pathlib import Path
from .data_manager import read_kindle_metadata, read_kindle_collection

# セル幅
cell_width_dict =   {
    "title":30,
    "authors":13,
    "publishers":10,
    "origin_type":10,
    "publication_date":10,
    "purchase_date":18,
    "kindle_url":6,
    "manga_url":6,
    "ASIN":13,
    "title_pron":10,
    "authors_pron":10,
    "series_pron":4,
    "series_num":4,
    "series_id":4,
    "collection_name":15,
    "collection_id":12
}
link_text_dict = {"kindle_url":"開く",
                  "manga_url":"開く"}
col_order = [

    'kindle_url','manga_url',
    'title', 
    'authors', 'publishers', 
    'title_pron', 'authors_pron',
    'origin_type',
    'publication_date','purchase_date',
    #  'series_pron',
    'series_num', 'series_id',
    'ASIN'

]
col_order_clctn = ["collection_name"]+col_order+["collection_id"]
col_dict = {
    "ASIN":"ASIN",
    "title_pron":"書カナ",
    "authors_pron":"著カナ",
    "title":"書籍名",
    "authors":"著者",
    "publishers":"出版社",
    "publication_date":"出版日",
    "purchase_date":"購入日",
    "origin_type":"取得元",
    "series_num":"シリーズNo.",
    "series_id":"シリーズID",
    "kindle_url":"PC",
    "manga_url":"漫画",
    "collection_name":"コレクション名",
    "collection_id":"collection_id"
}

cell_width_dict_jpn = {}
for key in col_dict.keys():
    if(key in cell_width_dict.keys()):
        cell_width_dict_jpn[col_dict[key]]=cell_width_dict[key]
cell_width_dict=cell_width_dict_jpn

link_text_dict_jpn = {}
for key in col_dict.keys():
    if(key in link_text_dict.keys()):
        link_text_dict_jpn[col_dict[key]]=link_text_dict[key]
link_text_dict = link_text_dict_jpn

def add_hyperlink_to_sheet(df,worksheet,url_format): 
    for link_col in link_text_dict.keys():
        if link_col not in df.columns:
            continue 
        # URL持つ列は何列目か
        idx = [i for i,col in enumerate(df.columns) if col==link_col][0]
        # ハイパーリンクに書き換え
        for row_num in range(1, len(df) + 1):
            cell_value = df.iloc[row_num - 1, idx]
            worksheet.write_url(row_num, idx, cell_value, url_format, string=link_text_dict[link_col])
    
def adjust_column_width(df,worksheet):
    sheet_name = worksheet.name
    for col in cell_width_dict: 
        if col in df.columns:
            idx = (df.columns==col).argmax() # 列番号取得
            worksheet.set_column(idx, idx, cell_width_dict[col]) # セル幅設定
    
def write_to_xlsx(df,sheet_name,writer,url_format):
    kindle_url = r"kindle://book/?action=open&asin={}"
    manga_url = r"https://read.amazon.co.jp/manga/{}"

    df["kindle_url"] = df["ASIN"].map(lambda x:kindle_url.format(x))
    df["manga_url"] = df["ASIN"].map(lambda x:manga_url.format(x))
    df["publication_date"]=df["publication_date"].dt.date
    
    if(sheet_name=='book'):
        df=df[col_order].sort_values(["purchase_date"],ascending=False).rename(columns=col_dict)
    elif(sheet_name=='collection'):
        df=df[col_order_clctn].sort_values(["collection_name","purchase_date"],ascending=False).rename(columns=col_dict)

    df.to_excel(writer,index=False, sheet_name=sheet_name)
    worksheet = writer.sheets[sheet_name]
    
    
    worksheet.freeze_panes(1, 0) # 1行目（ヘッダ）を固定
    worksheet.autofilter(0, 0, df.shape[0], df.shape[1]-1) # データフレーム全体をautofilter対象に
    
    add_hyperlink_to_sheet(df,worksheet,url_format)
    adjust_column_width(df,worksheet)

def write_formatted_excel(metadata_path,output_path):
    book_df = read_kindle_metadata(metadata_path)
    clctn_df = read_kindle_collection(metadata_path,book_df)

    kindle_url = r"kindle://book/?action=open&asin={}"
    manga_url = r"https://read.amazon.co.jp/manga/{}"

    with pd.ExcelWriter(Path(output_path)/'excel_shelf.xlsx') as writer:
        workbook = writer.book
        # ハイパーリンク用の書式を作成
        url_format = workbook.add_format({'color': 'blue', 'underline': 1}) 
            
        write_to_xlsx(book_df,'book',writer,url_format)
        write_to_xlsx(clctn_df,'collection',writer,url_format)