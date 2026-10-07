package com.fakao.growth;
import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.content.SharedPreferences;
import java.net.URI;
public class MainActivity extends Activity {
 private WebView web;
 private SharedPreferences prefs;
 @Override public void onCreate(Bundle b){
  super.onCreate(b);prefs=getSharedPreferences("connection",0);
  LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);
  Button connect=new Button(this);connect.setText("法官成长记 · 连接电脑 / 更换地址");connect.setOnClickListener(v->dialog());layout.addView(connect);
  web=new WebView(this);web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);
  web.setWebViewClient(new WebViewClient(){@Override public boolean shouldOverrideUrlLoading(WebView w,String url){return !allowed(url);}});
  layout.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(layout);
  String url=prefs.getString("url","");if(allowed(url))web.loadUrl(url);else dialog();
 }
 private boolean allowed(String text){try{URI uri=new URI(text);String h=uri.getHost();if(!"http".equals(uri.getScheme())||h==null)return false;String[] p=h.split("\\.");if(p.length!=4)return false;int a=Integer.parseInt(p[0]),b=Integer.parseInt(p[1]);for(String x:p){int n=Integer.parseInt(x);if(n<0||n>255)return false;}return a==10||(a==192&&b==168)||(a==172&&b>=16&&b<=31);}catch(Exception e){return false;}}
 private void dialog(){EditText box=new EditText(this);box.setSingleLine(true);box.setHint("http://192.168.1.100:8766");box.setText(prefs.getString("url",""));new AlertDialog.Builder(this).setTitle("输入电脑的局域网地址").setMessage("在电脑设置中开启局域网并重启，输入局域网IPv4地址；电脑需要保持运行。").setView(box).setPositiveButton("连接",(d,w)->{String u=box.getText().toString().trim();if(allowed(u)){prefs.edit().putString("url",u).apply();web.loadUrl(u);}else new AlertDialog.Builder(this).setMessage("请输入完整的局域网HTTP地址和端口").setPositiveButton("重试",(x,y)->dialog()).show();}).setNegativeButton("取消",null).show();}
 @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
}
