package info.androidapp.utils.cloud;

import info.androidapp.utils.http.RestfulClient;

import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.MalformedURLException;
import java.net.URL;
import java.util.HashMap;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.util.Log;

public class NetworkStatusDetector {
    private static final String TAG = "NetworkStatusDetector";
    private static NetworkStatusDetector instance;
    private static final long CACHE_TIMEOUT_MSEC = 5 * 60 * 1000; // 5min
    private HashMap<String, String> networkIsEnabledCache;
    private HashMap<String, String> canResolveDNSCache;
    private HashMap<String, String> canReachByHTTPCache;
    
    // singleton
    private NetworkStatusDetector(){
        networkIsEnabledCache = new HashMap<String, String>();
        canResolveDNSCache = new HashMap<String, String>();
        canReachByHTTPCache = new HashMap<String, String>();
    }

    public static NetworkStatusDetector getInstance(){
        if(null == instance){
            instance = new NetworkStatusDetector();
        }
        return instance;
    }
    /**
     * Androidのネットワーク状態を判定
     * @return
     */
    public boolean networkIsEnabled(Context context){
        long now = System.currentTimeMillis();
        String t = networkIsEnabledCache.get("lastTime");
        String r = networkIsEnabledCache.get("result");
        if(t != null && r != null){
            long lastTime = Long.parseLong(t);
            if(lastTime + CACHE_TIMEOUT_MSEC > now){
                // キャッシュ有効
                if("true".equals(r)){
                    return true;
                } else {
                    return false;
                }
            }
        }
        
        // キャッシュが無効の場合は実行して、キャッシュをアップデートする
        boolean result = checkNetworkIsEnabled(context);
        networkIsEnabledCache.put("lastTime", String.valueOf(now));
        networkIsEnabledCache.put("result", String.valueOf(result));
        return result;
    }
    
    private boolean checkNetworkIsEnabled(Context context){
        ConnectivityManager cMgr = (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo netInfo = cMgr.getActiveNetworkInfo();
        // TODO:netInfoがnullの場合はネットワークに繋がってない?
        if(null == netInfo){
            return false;
        }
        return netInfo.isAvailable();
    }

    /**
     * hostnameをDNSで引ければTrue
     * @param hostname
     * @return
     */
    public boolean canResolveDNS(String hostname){
        long now = System.currentTimeMillis();
        String t = canResolveDNSCache.get("lastTime");
        String r = canResolveDNSCache.get("result");
        String h = canResolveDNSCache.get("host");
        if(t != null && r != null && h != null){
            long lastTime = Long.parseLong(t);
            if(hostname.equals(h) && lastTime + CACHE_TIMEOUT_MSEC > now){
                // キャッシュ有効
                if("true".equals(r)){
                    Log.d(TAG, "true(cache)");   
                    return true;
                } else {
                    Log.d(TAG, "false(cache)");   
                    return false;
                }
            }
        }
        
        // キャッシュが無効の場合は実行して、キャッシュをアップデートする
        boolean result = checkCanResolveDNS(hostname);
        canResolveDNSCache.put("lastTime", String.valueOf(now));
        canResolveDNSCache.put("result", String.valueOf(result));
        canResolveDNSCache.put("host", hostname);
        Log.d(TAG, "result:" + result);   
        return result;
    }
    
    private boolean checkCanResolveDNS(String hostname){
        try{
            InetAddress.getByName(hostname);
        } catch (Exception e) {
            return false;
        }
        return true;
    }
    
    /**
     * tryToConnectUrlにHTTPまたはHTTPSでアクセスできればtrueを返す
     * @param tryToConnectUrl
     * @return
     */
    public boolean canReachByHTTP(String tryToConnectUrl){
        long now = System.currentTimeMillis();
        String t = canReachByHTTPCache.get("lastTime");
        String r = canReachByHTTPCache.get("result");
        String u = canReachByHTTPCache.get("url");
        if(t != null && r != null && u != null){
            long lastTime = Long.parseLong(t);
            if(tryToConnectUrl.equals(u) && lastTime + CACHE_TIMEOUT_MSEC > now){
                // キャッシュ有効
                if("true".equals(r)){
                    return true;
                } else {
                    return false;
                }
            }
        }
        
        // キャッシュが無効の場合は実行して、キャッシュをアップデートする
        boolean result = checkCanReachByHTTP(tryToConnectUrl);
        canReachByHTTPCache.put("lastTime", String.valueOf(now));
        canReachByHTTPCache.put("result", String.valueOf(result));
        canReachByHTTPCache.put("url", tryToConnectUrl);
        return result;
    }
    
    private boolean checkCanReachByHTTP(String tryToConnectUrl){
        URL url;
        try {
            url = new URL(tryToConnectUrl);
//            HttpURLConnection urlconn = (HttpURLConnection) url.openConnection();
//            urlconn.connect();
//            if(200 == urlconn.getResponseCode()){
//                return true;
//            }
            RestfulClient.get(tryToConnectUrl, null);
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
