var cstate = false;
var book_list = []
var series_list = []

var imgsize_slider;

var is_grid = true;
var is_reversed = false;

// オプションバーの設定
draw_option_bar();
document.getElementById("hidden_buttons").style.display = "none"

$(function() { //ヘッダーの高さ分だけコンテンツを下げる
  var height=$(".status_bar").height();
  $(".shelf_wrapeper").css("margin-top", height);
});

if(series_shelf_id==""){
  load_shelf_config(shelf_config_name);
}else{
  get_one_series();
}

//////////////////////////////////////////////////////////////////////////////////////

// 表示列数を指定してCSSに反映
function edit_style(colnum){
  $('.grid_wrapper').css({
      "grid-template-columns": "repeat("+colnum+", 1fr)"
  });
}

// 表紙画像の高さを設定
function edit_book_size(size){
  $('.horizontal_scroll_wrap').css({
    "height": size+"px",
    "padding": size*0.05+"px"
  });
  $('.scroll_item').css({
    "margin-right": size*0.03125+"px"
  });
  $('.serial_item').css({
    "width": size*0.8+"px",
  });
}

// GUIの表示
function draw_option_bar(){
  var hideButton = document.getElementById("hide_button");
  // GUIの表示非表示切り替え
  hideButton.onclick = function(){
    cstate = !cstate
    
    $(function() { //ヘッダーの高さ分だけコンテンツを下げる
      var height=$(".status_bar").height();
      $(".shelf_wrapeper").css("margin-top", height + 10);//10pxだけ余裕をもたせる
    });
    if(cstate){
      document.getElementById("hidden_buttons").style.display = "block"
    }else{
      document.getElementById("hidden_buttons").style.display = "none"
    }
  }
  // マウスオーバーとマウスアウトのイベントリスナーを追加
  hideButton.addEventListener('mouseenter', function(event) {
    event.target.style.backgroundColor = "rgba(135, 206, 250, 0.5)"; // 青色の半透明でハイライト
    event.target.style.outline = "1px solid lightskyblue"; // 青色の枠線
  });
  hideButton.addEventListener('mouseleave', function(event) {
    event.target.style.backgroundColor = ""; // 背景色をクリア
    event.target.style.outline = ""; // 枠線をクリア
  });

  if(series_shelf_id==""){ // 全シリーズ表示する本棚の場合
    // カラム数ドロップダウン
    var select_colnum = document.getElementById("colnum_dd")
    for(var i=1;i<=50;i++){
      var option_colnum =  document.createElement("option");
      option_colnum.setAttribute("value",i);
      option_colnum.innerHTML = i
      select_colnum.appendChild(option_colnum);
    }
    select_colnum[2].selected = true
    select_colnum.onchange = function(){
      // 選択されているoption要素を取得する
      var selectedItem = this.options[ this.selectedIndex ];
      edit_style(selectedItem.value);
    }

    // 本棚タイプのドロップダウン
    var select_shelf = document.getElementById("shelf_dd");
    var shelf_keys = ["series","author","collection"]
    for(var key of shelf_keys){
      var option_shelf =  document.createElement("option");
      option_shelf.setAttribute("value",key);
      option_shelf.innerHTML = key
      select_shelf.appendChild(option_shelf);
    }
    select_shelf.options[0].selected = true
    select_shelf.onchange = send_query;

    // ソートキーのドロップダウン
    var select_sort = document.getElementById("sort_dd");
    var sort_keys = ["rating","series_pron","author_pron","purchases",
                    "oldest_publication","latest_publication",
                    "oldest_purchase","latest_purchase"]
    for(var key of sort_keys){
      var option_sort =  document.createElement("option");
      option_sort.setAttribute("value",key);
      option_sort.innerHTML = key
      select_sort.appendChild(option_sort);
    }
    select_sort.options[0].selected = true
    select_sort.onchange = sort_shelf;

    // 昇順降順のドロップダウン
    var select_asc = document.getElementById("asc_dd");
    var asc_dict = {"DESC":"0","ASC":"1"}; // false/trueを入れてもsetAttributeすると文字列になるので。0,1にした
    for(var key of Object.keys(asc_dict)){
      var option_asc = document.createElement("option")
      option_asc.innerHTML = key
      option_asc.setAttribute("value",asc_dict[key])
      select_asc.appendChild(option_asc)
    }
    select_asc.options[0].selected = true
    select_asc.onchange = sort_shelf;

    // キーワードのテキストボックス
    var inputtext_keywords = document.getElementById("keyword_box")
    inputtext_keywords.onkeyup = function(){
      if( window.event.keyCode == 13 ){
        send_query();
      }
    };

    // クエリのテキストボックス
    var inputtext_query = document.getElementById("query_box")
    inputtext_query.onkeyup = function(){
      if( window.event.keyCode == 13 ){
        send_query();
      }
    };

    make_load_config_window();

  }else{  // 一つのシリーズのみを表示する本棚の場合
    is_grid = false
    document.getElementById("bookshelf").className = "serial_wrapper"
  }
  
  // 画像サイズのスライダー
  imgsize_slider = document.getElementById("imgsize_slider");
  imgsize_slider.addEventListener('input',(e)=>edit_book_size(imgsize_slider.value));  
}

function make_image_url(asin){
  var image_url = '../static/covers/'+asin+'.jpg';
  // var image_url = 'https://images-na.ssl-images-amazon.com/images/P/'+asin+'.09.LZZZZZZZ' // 直接参照する場合
  return image_url
}

function make_browser_url(asin){
  var browser_url = 'https://read.amazon.co.jp/manga/'+asin;
  return browser_url;
}

function make_kindle_url(asin){
  // var kindle_url = 'kindle://book/?action=open&asin='+asin;
  var kindle_url = 'https://read.amazon.co.jp/?asin='+asin;
  return kindle_url;
}

function sort_dictlist_by_key(key, is_asc) {
  if(['series_pron','author_pron'].includes(key)){ // 文字列の場合
    return (a, b) => {
      return is_asc=="1" ? a[key].localeCompare(b[key]) : b[key].localeCompare(a[key]);
    };
  }else{  // 数値の場合
    return (a,b)=>{
      var sign = is_asc=="1" ? 1:-1;
      if (a[key] > b[key]){return 1*sign;}
      else if (a[key] < b[key]){return -1*sign;}
      else{return 0;}
    }
  }
}

function draw_shelf(){
  document.getElementById("bookshelf").innerHTML=""
  if(series_list.length==0){return;}

  var emode_check = document.getElementById("edit_mode_check");
  if(is_grid){
    emode_check.disabled=false
    document.getElementById("bookshelf").classList.remove("serial_wrapper");
    document.getElementById("bookshelf").classList.add("grid_wrapper");
  }else{
    if(emode_check!=null){ // 単一シリーズページだと表示させない
      document.getElementById("edit_mode_check").disabled=true
    }
    document.getElementById("bookshelf").classList.remove("grid_wrapper");
    document.getElementById("bookshelf").classList.add("serial_wrapper");
  }
  if(document.getElementById("shelf_dd")!=null && document.getElementById("shelf_dd").value!="series"){  // series以外の場合は編集モードを非表示にする
    document.getElementById("edit_mode_check").checked=false
    document.getElementById("edit_mode_check").disabled=true
  }

  if(series_shelf_id==""){
    var sort_key = document.getElementById('sort_dd').value
    var is_asc = document.getElementById('asc_dd').value
    series_list.sort(sort_dictlist_by_key(sort_key,is_asc))
  }

  for(var i in series_list){
    var series_id = series_list[i].series_id
    var series_books = book_list.filter(function(bdl){
      return bdl["series_id"] == series_id
    });
    var series_title=series_list[i].series_title
    var shelf_type= series_list[i].shelf_type // (iの値によらず全て同じ)
    if(is_reversed){
      series_books.reverse();
    }

    var series_link_url = local_url+"/series_shelf?series_id="+encodeURIComponent(series_id);
    if(is_grid){ // グリッド表示の場合
      // シリーズ一つ分の棚
      var div_oneshelf = document.createElement('div');
      div_oneshelf.setAttribute("id","hsw_"+series_id);
      div_oneshelf.setAttribute("class","horizontal_scroll_wrap");
      
      // 表示するシリーズタイトル
      if(shelf_type!='series'){ // authorやcollectionの時だけ表示させる
        var div_series_title = document.createElement('div');
        div_series_title.setAttribute("class","series_name");
        div_series_title.innerHTML = series_title
        div_oneshelf.appendChild(div_series_title)
      }

      // シリーズページへのリンク
      var a_series_link = document.createElement('a');
      a_series_link.setAttribute("id","series_link_"+series_id);
      a_series_link.setAttribute("class","hidden_series_link");
      a_series_link.setAttribute("href",series_link_url);
      a_series_link.setAttribute("target","_blank");
      a_series_link.setAttribute("rel","noopener");
      div_oneshelf.appendChild(a_series_link)

      // マウスオーバー、マウスアウトイベントを追加
      a_series_link.addEventListener('mouseenter', function(event) {
        //マウスオーバーされたaタグの親要素をハイライト
        event.target.parentNode.style.backgroundColor = "rgba(135, 206, 250, 0.5)";
        event.target.parentNode.style.outline = "1px solid lightskyblue";
      });
      a_series_link.addEventListener('mouseleave', function(event) {
        //マウスアウトされたaタグの親要素のハイライト解除
        event.target.parentNode.style.backgroundColor = "";
        event.target.parentNode.style.outline = "";
      }
      );

      // URLパラメータとして本棚タイプの追加
      // クロージャを使用して a_series_link 要素を参照する
      // a_series_linkの参照先はforループで上書きされていくので、
      // クロージャ使わないとイベント発火時最後のa_series_linkが呼ばれることになる
      a_series_link.addEventListener("click", function(a_series_link) {
        return function(event) {
            event.preventDefault();
            var newURL = a_series_link.getAttribute("href") + "&shelf_type=" + encodeURIComponent(document.getElementById("shelf_dd").value);
            window.open(newURL, "_blank");
        };
      }(a_series_link));

      // 評価情報ボックス
      var div_param_box = document.createElement('div');
      div_param_box.setAttribute("id","series_param_"+series_id);
      div_param_box.setAttribute("class","param_box");
      div_oneshelf.appendChild(div_param_box)

      // 棚の中身リスト
      var ul_scroll_lst = document.createElement('ul');
      ul_scroll_lst.setAttribute("class","scroll_lst");
      for(var j in series_books){
        var asin = series_books[j]["ASIN"]
        // 本一冊
        var li_scroll_item = document.createElement('li');
        li_scroll_item.setAttribute("class","scroll_item");

        // カバー
        var browser_url = make_browser_url(asin);
        var a_cover = document.createElement('a');
        a_cover.setAttribute("class","cover");
        a_cover.setAttribute("href",browser_url);
        a_cover.setAttribute("asin",asin);
        a_cover.setAttribute("series_id",series_id);
        a_cover.setAttribute("target","_brank");

        // カバー画像
        var image_url = make_image_url(asin);
        var img_cover = document.createElement('img');
        img_cover.setAttribute("src",image_url)

        a_cover.appendChild(img_cover)
        li_scroll_item.appendChild(a_cover)
        ul_scroll_lst.appendChild(li_scroll_item)
        div_oneshelf.appendChild(ul_scroll_lst)

        if(j>0){
          li_scroll_item.classList.add("continued")
        }else{
          li_scroll_item.classList.add("first")
        }
      }
      document.getElementById("bookshelf").appendChild(div_oneshelf)
    }else{  // シリアル表示の場合
      for(var j in series_books){
        var asin = series_books[j]["ASIN"]
        var serial_item = document.createElement('div');
        serial_item.setAttribute("class","serial_item");

        // カバー画像
        var browser_url = make_browser_url(asin);
        var a_cover = document.createElement('a');
        a_cover.setAttribute("class","cover_w");
        a_cover.setAttribute("href",browser_url);
        a_cover.setAttribute("asin",asin);
        a_cover.setAttribute("series_id",series_id);
        a_cover.setAttribute("target","_brank");

        var image_url = make_image_url(asin);
        var img_cover = document.createElement('img');
        img_cover.setAttribute("src",image_url)

        a_cover.appendChild(img_cover)
        serial_item.appendChild(a_cover)
        document.getElementById("bookshelf").appendChild(serial_item)
        if(j>0){
          serial_item.classList.add("continued")
        }else{
          serial_item.classList.add("first")
        }
      }
    }
  }
  const coverElements = document.querySelectorAll(".cover, .cover_w");
  coverElements.forEach(function (a_cover) {
    a_cover.addEventListener("click", function (event) {
      if (event.ctrlKey && event.shiftKey) { // カバー画像をShift+Ctrl+クリックでkindle for pcを開く
        event.preventDefault();
        const asin = a_cover.getAttribute("asin");
        const kindle_url = make_kindle_url(asin);
        window.open(kindle_url);
      }
    });
  });

  // 再描画により改変されたCSSが適用されなくなるため、設定しなおす
  edit_book_size(imgsize_slider.value)
  switch_show_all()
  

  if(is_grid){
    // rating表示状態を前回と同様にする
    switch_show_rating()
    
    // 慣性スクロール設定
    // Copyright (c) 2020 https://www.it-the-best.com https://www.it-the-best.com/entry/jquery-plugin-mousedragscroll
    $(".scroll_lst").setListmousedragscroll({"inertia":true,"loop":false});
  }
}

// グリッド表示とシリアル表示の切り替え
function switch_shelf(){
  is_grid = !is_grid
  draw_shelf()
  draw_rating()
}

// 棚内の順序逆転
function reverse_shelf(){
  is_reversed = !is_reversed
  draw_shelf()
  draw_rating()
}

// 本棚の並び替え
function sort_shelf(){
  draw_shelf()
  draw_rating()
}

// 評価情報ボックスの描画
function draw_rating(){
  if(is_grid==false){return} // grid表示ではない場合スキップ
  if(document.getElementById("show_all_mode")==null){return}// one series shelfの場合スキップ
  var tabindex=100;
  for(var series_i of series_list){
      var table_param = document.createElement("table")
      table_param.setAttribute("class","param_table")
      var param_names = ["rating","tags"];
      for(var param_name of param_names){
        var tr_param = document.createElement("tr")
        var td_param_name = document.createElement("td")
        td_param_name.innerHTML = param_name
        var td_input_param = document.createElement("td")
        var input_param = document.createElement("input")
        input_param.setAttribute("type","text")
        input_param.setAttribute("value",series_i[param_name])
        input_param.setAttribute("id",series_i.series_id+'_'+param_name)
        input_param.setAttribute("tabindex",tabindex)
        input_param.setAttribute("size",10)
        input_param.setAttribute("onfocus","this.select();")
        td_input_param.appendChild(input_param)

        tr_param.appendChild(td_param_name)
        tr_param.appendChild(td_input_param)

        table_param.appendChild(tr_param)
        tabindex += 1;
      }
      document.getElementById('series_param_'+series_i.series_id).appendChild(table_param)
  }
}

// 評価情報ボックスの表示/非表示切り替え
function switch_show_rating(){
  var related_ids = ["switchshelf_btn"
                    ,"sort_dd","asc_dd","keyword_box","query_box"
                    ,"apply1","apply2","shelf_dd"]
  if(document.getElementById("edit_mode_check").checked){
    document.getElementById("apply_rating").disabled=false;
    for(rid of related_ids){
      document.getElementById(rid).disabled = true;
    }
    $('.param_box').css({"display": "block"});
  }else{// 編集表示を消す
    document.getElementById("apply_rating").disabled=true;
    for(rid of related_ids){
      document.getElementById(rid).disabled = false;
    }
    $('.param_box').css({"display": "none"});
  }
}

function switch_show_all(){
  if(document.getElementById("show_all_mode")==null){return}// one series shelfの場合スキップ
  if(document.getElementById("show_all_mode").checked){
    for(var item of document.getElementsByClassName("first")){
      var a_cover = item.childNodes[0];
      var asin = a_cover.getAttribute("asin");
      var browser_url = make_browser_url(asin);
      a_cover.setAttribute("href",browser_url);
    }
    $('.continued').css({
      "display": "inline-block"
    });
  }else{
    for(var item of document.getElementsByClassName("first")){
      var a_cover = item.childNodes[0];
      var series_id = a_cover.getAttribute("series_id");
      var series_link_url = local_url+"/series_shelf?series_id="+series_id;
      a_cover.setAttribute("href",series_link_url);
    }
    $('.continued').css({
      "display": "none"
    });
  }
}

// 評価情報を送信
function update_rating(){
  for(i in series_list){
      elm = series_list[i]
      // if(document.getElementById(elm.series_id+"_rating")==null){continue}
      elm.rating = Number(document.getElementById(elm.series_id+"_rating").value) // Number()は数字以外が入っているとnullになる
      elm.tags = document.getElementById(elm.series_id+"_tags").value
      elm.tags = elm.tags=="undefined" ? null:elm.tags // tagsは文字列にしているため、nullを文字列としてとってしまうので変換。
  }
  edit_series_review({"series_param":series_list});
}

// オプションバーから設定値を取得しクエリを投げる
function send_query(){
  data_dict = {
    "shelf_keys":document.getElementById("shelf_dd").value,
    "keywords":document.getElementById("keyword_box").value,
    "query":document.getElementById("query_box").value
  }
  // console.log(data_dict["shelf_keys"])

  var edit_check = document.getElementById("edit_mode_check")
  if(data_dict["shelf_keys"]!='series'){ // ここでこれを設定してもcall_api->draw_shelfで上書きされるのでおそらく意味ない
    edit_check.checked=false
    edit_check.disabled=true
  }else{
    edit_check.disabled=false
  }
  switch_show_rating()

  call_api("get_book_info",arg_data={"data":data_dict})
}

function log_ajax_fail(jqXHR, textStatus, errorThrown){
  console.log(textStatus,jqXHR,errorThrown);
  console.log(jqXHR);
  console.log(errorThrown);
  alert(textStatus);
}

// ロードアイコンを表示する関数
function showLoadingIcon() {
  $("#loading-modal").show();
}
// ロードアイコンを非表示にする関数
function hideLoadingIcon() {
  $("#loading-modal").hide();
}

// オプションバーから設定値を取得しクエリを投げて保存する
function save_shelf_config(){
  showLoadingIcon();
  data_dict = {
    "shelf_keys":document.getElementById("shelf_dd").value,
    "colnum":document.getElementById("colnum_dd").value,
    "imgsize":document.getElementById("imgsize_slider").value,
    "sort_keys":document.getElementById("sort_dd").value,
    "is_asc":document.getElementById("asc_dd").value,
    "keywords":document.getElementById("keyword_box").value,
    "query":document.getElementById("query_box").value,
    "show_all_mode":document.getElementById("show_all_mode").checked,
    "is_grid":is_grid,
    "is_reversed":is_reversed
  }
  $.ajax({
    type: 'POST',
    url : local_url+'/save_shelf_config',
    data: JSON.stringify({"data":data_dict,"name":document.getElementById("config_box").value}),
    contentType:'application/json'
  }).done(function(res,textStatus,jqXHR){
    console.log("saved");
  }).fail(log_ajax_fail).always(hideLoadingIcon);
  // 閉じる
  const overlay = document.getElementById('overlay');
  overlay.style.display = 'none';
}

function load_shelf_config(shelf_config_name){
  $.ajax({
    type: 'POST',
    url : local_url+"/load_shelf_config",
    data: JSON.stringify({"name":shelf_config_name}),
    contentType:'application/json'
  }).done(function(res,textStatus,jqXHR){
    document.getElementById("shelf_dd").value=res["shelf_keys"]
    document.getElementById("sort_dd").value=res["sort_keys"]
    document.getElementById("asc_dd").value=res["is_asc"]
    document.getElementById("keyword_box").value=res["keywords"]
    document.getElementById("query_box").value=res["query"]
    document.getElementById("show_all_mode").checked=res["show_all_mode"]
    is_grid=res["is_grid"]
    is_reversed=res["is_reversed"]
    document.getElementById("colnum_dd").value=res["colnum"]
    document.getElementById("imgsize_slider").value=res["imgsize"]
    send_query();

    // draw_rating();
  }).fail(function(jqXHR, textStatus, errorThrown) {
    console.log(textStatus,jqXHR,errorThrown);
    console.log(jqXHR);
    console.log(errorThrown);
    alert(textStatus);
  });
}

// 本棚設定保存・ロード画面
function make_load_config_window(){
  const openButton = document.getElementById('openButton');
  const overlay = document.getElementById('overlay');
  const closeButton = document.getElementById('closeButton');

  openButton.addEventListener('click', () => {
    overlay.style.display = 'flex';
    get_shelf_config_list();
  });
  closeButton.addEventListener('click', () => {
    overlay.style.display = 'none';
  });
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      overlay.style.display = "none";
    }
  });
}

// フォルダから本棚設定jsonのリストを取得
function get_shelf_config_list(){
  $.ajax({
    type: 'POST',
    url : local_url+"/get_shelf_config_list",
    data: JSON.stringify({}),
    contentType:'application/json'
  }).done(function(res,textStatus,jqXHR){
    console.log("done")
    var shelf_config_list = res["shelf_config_list"]
    var ul_config = document.getElementById('config_ul');
    ul_config.innerHTML="";
    if(shelf_config_list.length>0){
      for(var sc of shelf_config_list){
        var li_config = document.createElement("li");
        li_config.style.display = "flex"; // 横並びにするためにflexboxを使用
        li_config.style.alignItems = "center"; // 垂直方向中央揃え

        var span_config_name = document.createElement("span");
        span_config_name.textContent = sc;
        span_config_name.style.marginRight = "10px"; // 右に少しスペースを空ける
        li_config.appendChild(span_config_name);

        var btn_apply = document.createElement("button");
        btn_apply.setAttribute("onclick", `load_shelf_config('${sc}');`);
        btn_apply.textContent = "適用";
        li_config.appendChild(btn_apply);

        if (sc !== "default") {
          var btn_delete = document.createElement("button");
          btn_delete.textContent = "削除";
          btn_delete.style.marginLeft = "5px"; // 左に少しスペースを空ける
          btn_delete.setAttribute("onclick", `delete_shelf_config('${sc}');`);
          li_config.appendChild(btn_delete);
        }

        ul_config.appendChild(li_config);
      }
    }
  }).fail(log_ajax_fail);
}

function delete_shelf_config(config_name) {
  if (confirm(`設定「${config_name}」を本当に削除しますか？`)) {
    showLoadingIcon();
    $.ajax({
      type: 'POST',
      url: local_url + '/delete_shelf_config',
      data: JSON.stringify({ "name": config_name }),
      contentType: 'application/json'
    }).done(function (res, textStatus, jqXHR) {
      console.log("deleted");
      get_shelf_config_list(); // リストを再読み込みして更新
    }).fail(log_ajax_fail).always(hideLoadingIcon);
  }
}

function get_one_series(){
  data_dict = {
    "query":"series_id=='"+series_shelf_id+"'",
    "shelf_keys":series_shelf_type
  }
  call_api("get_book_info",arg_data={"data":data_dict})
}

// データをロードし、結果を描画する
function call_api(api,arg_data={"data":null}){
  showLoadingIcon();
  $.ajax({
      type: 'POST',
      url : local_url+"/"+api,
      data: JSON.stringify(arg_data),
      contentType:'application/json'
  }).done(function(res,textStatus,jqXHR){
      book_list = res["book"];
      series_list = res["series"];
      draw_shelf();
      draw_rating();
      
      let col_elem = document.getElementById("colnum_dd");
      if (col_elem) {  // シリーズ棚ではカラムがない
        edit_style(document.getElementById("colnum_dd").value);
        edit_book_size(document.getElementById("imgsize_slider").value);
      }
  }).fail(log_ajax_fail).always(hideLoadingIcon);
}

// 評価情報を編集し、再描画する
function edit_series_review(series_dl_js){
  showLoadingIcon();
  $.ajax({
      type: 'POST',
      url : local_url+'/edit_series_review',
      data: JSON.stringify(series_dl_js),
      contentType:'application/json'
    }).done(function(res,textStatus,jqXHR){
      send_query();
  }).fail(log_ajax_fail).always(hideLoadingIcon);
}