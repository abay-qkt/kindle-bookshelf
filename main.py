## pyinstallerを使用する場合エンコーディングエラーが発生するため
## 以下のコードを実行
## 参考: https://blog.tsukumijima.net/article/python3-windows-unicodedecodeerror-hack/
## 参考: https://stackoverflow.com/questions/31469707/changing-the-locale-preferred-encoding-in-python-3-in-windows
import os
if os.name == 'nt':
    import _locale
    _locale._getdefaultlocale_backup = _locale._getdefaultlocale
    _locale._getdefaultlocale = (lambda *args: (_locale._getdefaultlocale_backup()[0], 'UTF-8'))
## ----------------------------------------------------------------------------------------------------------

from flask import Flask, Response, render_template, send_from_directory, request
import simplejson
import pandas as pd
from models.data_manager import DataManager
from models.excel_writer import write_formatted_excel
from pathlib import Path
import threading
import webbrowser
import tkinter as tk
import argparse
from trial_mode import TrialManager

# コマンドライン引数の処理
parser = argparse.ArgumentParser()
parser.add_argument("--trial", action="store_true", help="Run in trial mode")
args = parser.parse_args()

trial_manager = TrialManager(enabled=args.trial)  # True or False
# 使用方法 python main.py --trial

shelf_info_path = Path("shelf_info/")
bookcovers_path = Path("static/")

if(not shelf_info_path.exists()):
	shelf_info_path.mkdir()

settings_path = shelf_info_path/"settings.json"
default_settings = {
	"metadata_path":str(Path.home()/"AppData/Local/Amazon/Kindle/Cache/"),
	"local_ip":"127.0.0.1",
	"port":5000
}
if(not settings_path.exists()):
	with open(settings_path, "w") as f:
		simplejson.dump(default_settings,f,indent=4)

with open(shelf_info_path/"settings.json", "r") as f:
	settings = simplejson.load(f)

metadata_path = Path(settings["metadata_path"])
local_ip = "127.0.0.1" # settings["local_ip"] # 基本127.0.0.1以外ないので決め打ち。ただ、0.0.0.0使う可能性考えてjsonの情報はそのままにしておく
local_url = 'http://{}:{}'.format(local_ip,settings["port"])

shelf_configs_path = shelf_info_path/"shelf_configs"
if(not shelf_configs_path.exists()):
	shelf_configs_path.mkdir()
default_shelf = {
	"colnum": "3",
	"imgsize": "160",
	"sort_keys": "latest_purchase",
	"is_asc": "0",
	"keywords": "",
	"query": "",
	"show_all_mode": True,
	"is_grid": True,
	"is_reversed":False,
	"shelf_keys": "series"
}
with open(shelf_configs_path/"default.json","w") as f:
	simplejson.dump(default_shelf,f,indent=4)


shelf_config_js_path = Path("static/shelf_config_name.js")
if(not (shelf_config_js_path).exists()):
	with open(shelf_config_js_path, "w") as f:
		f.write("var shelf_config_name='default'")

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# デバッグモードを無効にし、リローダーとデバッガーも無効に設定
app.debug = False
app.use_reloader = False
app.use_debugger = False

# Tkinter GUIの準備
root = tk.Tk()
root.title("Kindle Book Shelf")
root.geometry("300x100")
status_label = tk.Label(root, text="アプリ起動中...")
status_label.pack()
# ハイパーリンクを表示
link_label = tk.Label(root, text=local_url, fg="blue", cursor="hand2")
link_label.pack()
link_label.bind("<Button-1>", lambda e: open_url(local_url))

def update_status(text):
    """Tkinterのラベルを更新する関数"""
    status_label.config(text=text)
    root.update()  # GUIを更新

def open_url(url):
    """URLをブラウザで開く関数"""
    webbrowser.open(url)

@app.route('/')
def main_view():
    update_status("データ更新中...")
    update_info()
    update_status("準備完了")
    
    return render_template('index.html', local_url=local_url ,series_shelf_id="",series_shelf_type="",trial_mode=trial_manager.enabled)

@app.route('/series_shelf')
def series_view():
	if request.args.get("series_id") is not None:
		series_id = request.args.get('series_id')
		shelf_type = request.args.get('shelf_type')
	else:
		series_id = None
	return render_template('index.html', local_url=local_url, series_shelf_id=series_id, series_shelf_type=shelf_type)

@app.route('/save_shelf_config',methods=["POST"])
def save_shelf_config():
	reqjson = request.json["data"]
	config_name = request.json["name"]+".json"
	if config_name=='.json': # 何も入力されていなかった場合
		return {}
	with open(shelf_configs_path/config_name, "w") as f:
		simplejson.dump(reqjson,f,indent=4)
	return {}

@app.route('/load_shelf_config',methods=["POST"])
def load_shelf_config():
	config_name = request.json["name"]
	shelf_config_file = shelf_configs_path/(config_name+".json")
	if not shelf_config_file.exists():# 前回のshelf_configのファイルが存在しない場合
		config_name = "default"
		shelf_config_file = shelf_configs_path/(config_name+".json")

	with open(shelf_config_file, "r") as f:
		shelf_config = simplejson.load(f)
	with open(shelf_config_js_path, "w") as f:
		f.write("var shelf_config_name='"+config_name+"'")
	return Response(simplejson.dumps(shelf_config,ignore_nan=True),mimetype="application/json")

@app.route('/delete_shelf_config',methods=["POST"])
def delete_shelf_config():
	config_name = request.json["name"]
	shelf_config_file = shelf_configs_path/(config_name+".json")
	if shelf_config_file.exists():
		shelf_config_file.unlink()
	return Response(simplejson.dumps(None),mimetype="application/json")

@app.route('/get_shelf_config_list',methods=["POST"])
def get_shelf_config_list():
	path_list = sorted(shelf_configs_path.glob("*.json"))
	config_list = [path.stem for path in path_list]
	return Response(simplejson.dumps({"shelf_config_list":config_list},ignore_nan=True),mimetype="application/json")

@app.route('/get_book_info',methods=["POST"])
def get_book_info():
	book_df = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='book')
	series_df = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='series')

	book_df = pd.merge(book_df,series_df,on='series_id',how='left')

	# 著者名をseries_idにした場合も想定したソート
	# シリーズの初出版日→シリーズ内の出版日(→タイトルの読み仮名)　の順でソート
	series_first_publication_date = book_df.groupby("series_id")["publication_date"].min().rename("series_first_publication_date").reset_index()
	book_df = pd.merge(book_df,series_first_publication_date,on='series_id',how='left')
	book_df = book_df.sort_values(["series_first_publication_date","publication_date","title_pron"])
	book_df = book_df.drop(["series_first_publication_date"],axis=1)

	reqjson = request.json["data"]
	if(reqjson):
		print(reqjson)
		if("shelf_keys" in reqjson.keys()):
			if(reqjson["shelf_keys"])=='author':
				# 漫画シリーズにおいて著者が複数いる場合、Amazon側の登録漏れで一部の巻だけ著者１名の場合が多々ある
				# それを修正する。（実際に一部の巻だけ著者が１名になるケースは存在するが、登録漏れを修正することを優先）
				authors_dict = book_df.groupby("series_id")["authors"].apply(lambda x:x[x.fillna("").str.len().idxmax()]).to_dict()
				authors_pron_dict = book_df.groupby("series_id")["authors_pron"].apply(lambda x:x[x.fillna("").str.len().idxmax()]).to_dict()
				book_df["authors"] = book_df["series_id"].map(authors_dict)
				book_df["authors_pron"] = book_df["series_id"].map(authors_pron_dict)

				book_df["series_id"] = book_df["authors"]
				book_df["series_title"] = book_df["authors"].fillna("").map(lambda x:x if len(x)<35 else x[:35]+"...")
			elif(reqjson["shelf_keys"]=='collection'):
				clctn_df = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='collection')
				clctn_df = clctn_df.drop(["last_updated_timestamp"],axis=1).sort_values(["publication_date","title"])
				book_df = pd.merge(clctn_df,book_df[["ASIN","rating","tags"]],on='ASIN',how='left')
				book_df["series_id"] = book_df["collection_id"]
				book_df["series_title"] = book_df["collection_name"]
			else:
				book_df["series_title"] = book_df["series_id"]
		def agg_series_info(x):
			ret = {}
			ret["rating"] = x["rating"].max()
			ret["tags"] = "/".join(x["tags"].drop_duplicates().fillna(""))

			ret["purchases"] = x.shape[0]
			ret["series_pron"] = x["series_pron"].iloc[0]
			ret["author_pron"] = x["authors_pron"].iloc[0]

			ret["series_title"] = x["series_title"].iloc[0]

			ret["oldest_publication"] = x["publication_date"].min()
			ret["latest_publication"] = x["publication_date"].max()
			ret["oldest_purchase"] = x["purchase_date"].min()
			ret["latest_purchase"] = x["purchase_date"].max()

			keywords = [x["title"].iloc[0]]
			keywords.extend(set(x["authors"].fillna("")))
			keywords.extend(set(x["publishers"].fillna("")))
			ret["keywords"] = " ".join(keywords).upper()

			return pd.Series(ret)

		series_df =   (book_df
						.groupby("series_id")
						.apply(agg_series_info)
						.reset_index())
		
		if("keywords" in reqjson.keys() and reqjson["keywords"]!=""):
			series_df = series_df[series_df["keywords"].str.contains("|".join(reqjson["keywords"].upper().replace("　"," ").split(" ")))].copy()
		if("query" in reqjson.keys() and reqjson["query"]!=""):
			series_df = series_df.query(reqjson["query"]).copy()

		date_cols = ["oldest_publication","latest_publication",
					 "oldest_purchase","latest_purchase"]
		series_df[date_cols] = series_df[date_cols].astype("int64")//10**9  # json化するために数値にする	
		if("shelf_keys" in reqjson.keys()):
			series_df["shelf_type"]=reqjson["shelf_keys"] # データフレームだけ見てもseries_idが何を示しているかわかるように

	# json化するために数値に戻す	
	book_df["publication_date"] = book_df["publication_date"].astype("int64")//10**9
	book_df["purchase_date"] = book_df["purchase_date"].astype("int64")//10**9

	book_dict = book_df.to_dict(orient="records")
	series_dict =  series_df.to_dict(orient="records")
	ret_dict = {"book":book_dict,"series":series_dict}
	# nanをnullにするため、flaskのjsonifyは使わずsimplejsonを使う
	return Response(simplejson.dumps(ret_dict,ignore_nan=True),mimetype="application/json")

@app.route('/edit_series_review', methods=["POST"])
def edit_series_review():
	series_dict = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='series').set_index("series_id")
	added_dict = pd.DataFrame.from_dict(request.json["series_param"]).set_index("series_id")
	series_dict.loc[added_dict.index,["rating","tags"]] = added_dict.loc[:,["rating","tags"]]
	series_df = series_dict.reset_index()
	book_df = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='book')
	clctn_df = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='collection')
	with pd.ExcelWriter(shelf_info_path/'shelf_info.xlsx') as writer:
		book_df.to_excel(writer, index=False, sheet_name='book')  
		series_df.to_excel(writer, index=False, sheet_name='series')  
		clctn_df.to_excel(writer, index=False, sheet_name='collection') 
	return {}

# @app.route('/update_info',methods=["POST"])
def update_info():
	data_manager = DataManager(metadata_path,shelf_info_path,bookcovers_path)
	data_manager.update_from_kindle()
	# return get_book_info()

@app.route('/favicon.ico')
def favicon():
	return send_from_directory(app.root_path+"/static/","favicon.ico")


def run_flask():
    update_status("Excelファイル作成中...")
    write_formatted_excel(metadata_path,output_path="..") # 3秒程度要する
    update_status("Flask起動中...")
    app.run(host=local_ip,port=settings["port"])

if __name__ == '__main__':
    # Flaskは別スレッドで起動
    threading.Thread(target=run_flask, daemon=True).start()

    # ブラウザ自動起動（オプション）
    webbrowser.open(local_url)

    root.mainloop()
