import requests
import time
import shutil
import hashlib
from pathlib import Path
from tqdm import tqdm
import platform

class BookCoverManager():
    def __init__(self,metadata_path,bookcovers_path):
        self.bookcovers_path = Path(bookcovers_path)
        system = platform.system()
        if system == 'Windows':
            self.bookcover_addresses = [
                {
                    "src_path":Path(metadata_path)/"Caches/covers",
                    "save_path":Path(self.bookcovers_path/"covers")
                }
            ]
        else:
            self.bookcover_addresses = [
                {
                    "src_url":'https://images-na.ssl-images-amazon.com/images/P/{}.09.LZZZZZZZ',
                    "save_path":Path(self.bookcovers_path/"covers")
                }
            ]
        for address in self.bookcover_addresses:
            if(not address["save_path"].exists()):
                address["save_path"].mkdir()

    def add_bookcovers(self, book_df):
        # 所有書籍のASINと表紙画像フォルダ内ののASINを比較
        # 表紙画像フォルダ内にない所有書籍のASINの表紙画像を取得
        for address in tqdm(self.bookcover_addresses):
            exists_bookcovers = [path.name.split(".")[0] for path in address["save_path"].glob("*")]    
            target_bookcovers = set(book_df["ASIN"]) - set(exists_bookcovers)

            if "src_path" in address.keys(): # Kindle for PC のキャッシュ画像をコピー
                for asin in target_bookcovers:
                    asin_md5 = hashlib.md5(asin.encode()).hexdigest().upper() # ファイル名はASINのmd5ハッシュ
                    from_path = address["src_path"]/(asin_md5+".jpg")
                    to_path   = address["save_path"]/(asin+".jpg")
                    if(from_path.exists()):
                        shutil.copy2(from_path,to_path)
            else:  # amazonのURLから画像を取得
                for asin in tqdm(target_bookcovers):
                    url = address["src_url"].format(asin)
                    file_name = address["save_path"]/(Path(url).name.split(".")[0]+".jpg")
                    rq = requests.get(url, stream=True)
                    if rq.status_code == 200:
                        with open(file_name, 'wb') as f:
                            f.write(rq.content)