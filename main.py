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
from pathlib import Path

shelf_info_path = Path("shelf_info/")
bookcovers_path = Path("static/")

if(not shelf_info_path.exists()):
	shelf_info_path.mkdir()

settings_path = shelf_info_path/"settings.json"
if(not settings_path.exists()):
	with open(settings_path, "w") as f:
		simplejson.dump({"metadata_path":None,"local_ip":None,"port":5000},f,indent=4)

with open(Path(shelf_info_path)/"settings.json", "r") as f:
	settings = simplejson.load(f)

if(settings["metadata_path"]):
	metadata_path = Path(settings["metadata_path"])
else:
	metadata_path = Path.home()/"AppData/Local/Amazon/Kindle/Cache/"

if(settings["local_ip"]):
	local_ip = settings["local_ip"] 
else:
	local_ip = "127.0.0.1"
local_url = 'http://{}:{}'.format(local_ip,settings["port"])

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

@app.route('/')
def main_view():
	update_info()
	return render_template('index.html', local_url=local_url ,series_shelf_id="")

@app.route('/series_shelf')
def series_view():
	if request.args.get("series_id") is not None:
		series_id = request.args.get('series_id')
	else:
		series_id = None
	return render_template('index.html', local_url=local_url, series_shelf_id=series_id)

@app.route('/get_book_info',methods=["POST"])
def get_book_info():
	book_df = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='book')
	series_df = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='series')

	series_df = series_df.sort_values(["rating"],ascending=False)
	
	book_df["purchase_timing"] = (book_df["purchase_date"]-book_df["publication_date"]).dt.total_seconds()

	reqjson = request.json["data"]
	if(reqjson):
		print(reqjson)
		if("sort_keys" in reqjson.keys() and reqjson["sort_keys"] in ["oldest_publication","latest_publication","early_purchase","late_purchase"]):
			book_df = book_df[book_df["publication_date"]!="2200-01-01 00:00:00"]  # 発行日に基づくソートの場合、発行日が欠損の物は除外
		if("sort_keys" in reqjson.keys() and reqjson["sort_keys"]!="rating"):
			book_df = book_df[book_df["series_id"]!="no_series_id"] # シリーズのソートの邪魔になるためシリーズもの以外は除外
		def agg_series_info(x):
			ret = {}
			ret["purchases"] = x.shape[0]
			ret["series_pron"] = x["series_pron"].iloc[0]
			ret["author_pron"] = x["authors"].iloc[0]

			ret["oldest_publication"] = x["publication_date"].min()
			ret["latest_publication"] = x["publication_date"].max()
			ret["oldest_purchase"] = x["purchase_date"].min()
			ret["latest_purchase"] = x["purchase_date"].max()
			ret["early_purchase"] = x["purchase_timing"].min()
			ret["late_purchase"]  = x["purchase_timing"].max()

			keywords = [x["title"].iloc[0]]
			keywords.extend(set(x["authors"].fillna("")))
			keywords.extend(set(x["publishers"].fillna("")))
			ret["keywords"] = " ".join(keywords).upper()

			return pd.Series(ret)

		additional_info =   (book_df.sort_values("series_num")
							.groupby("series_id")
							.apply(agg_series_info))
		series_df = pd.merge(series_df,additional_info , on="series_id", how="left")

		series_df = series_df[series_df["series_id"].isin(book_df["series_id"].unique())]  # bookを持たないseriesを削除

		if("sort_keys" in reqjson.keys()):
			series_df = series_df.sort_values(reqjson["sort_keys"],ascending=int(reqjson["is_asc"]))
		if("keywords" in reqjson.keys() and reqjson["keywords"]!=""):
			series_df = series_df[series_df["keywords"].str.contains("|".join(reqjson["keywords"].upper().replace("　"," ").split(" ")))]
		if("query" in reqjson.keys() and reqjson["query"]!=""):
			series_df = series_df.query(reqjson["query"])

		date_cols = ["oldest_publication","latest_publication",
					 "oldest_purchase","latest_purchase",
					 "early_purchase","late_purchase"]
		series_df[date_cols] = series_df[date_cols].astype("int64")//10**9  # json化するために数値にする	

	# json化するために数値に戻す	
	book_df["publication_date"] = book_df["publication_date"].astype("int64")//10**9
	book_df["purchase_date"] = book_df["purchase_date"].astype("int64")//10**9

	book_dict = book_df.sort_values("series_num").to_dict(orient="records")
	series_dict =  series_df.to_dict(orient="records")
	ret_dict = {"book":book_dict,"series":series_dict}
	# nanをnullにするため、flaskのjsonifyは使わずsimplejsonを使う
	return Response(simplejson.dumps(ret_dict,ignore_nan=True),mimetype="application/json")

@app.route('/edit_series_review', methods=["POST"])
def edit_series_review():
	series_dict = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='series').set_index("series_id")
	added_dict = pd.DataFrame.from_dict(request.json["series_param"]).set_index("series_id")
	series_dict.loc[added_dict.index,series_dict.columns] = added_dict.loc[:,series_dict.columns]
	series_df = series_dict.reset_index()
	book_df = pd.read_excel(shelf_info_path/'shelf_info.xlsx',sheet_name='book')
	with pd.ExcelWriter(shelf_info_path/'shelf_info.xlsx') as writer:
		book_df.to_excel(writer, index=False, sheet_name='book')  
		series_df.to_excel(writer, index=False, sheet_name='series')  
	return {}

# @app.route('/update_info',methods=["POST"])
def update_info():
	data_manager = DataManager(metadata_path,shelf_info_path,bookcovers_path)
	data_manager.update_from_kindle()
	# return get_book_info()

@app.route('/favicon.ico')
def favicon():
	return send_from_directory(app.root_path+"/static/","favicon.ico")


if __name__ == "__main__":
	if(local_ip=="127.0.0.1"):
		app.run(port=settings["port"])	
	else:
		app.run(host="0.0.0.0",port=settings["port"])
		
