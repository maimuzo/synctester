package info.androidapp.utils.cloud;


import info.androidapp.utils.http.RestfulClient;
import info.androidapp.utils.http.RestfulClient.CustomPullParser;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.apache.http.client.HttpResponseException;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.AsyncTask;
import android.telephony.TelephonyManager;
import android.util.Log;
import android.widget.Toast;

public class CloudSyncronizer {
    private static final String TAG = "CloudSyncronizer";
    public static final String RESULT_STATE_NOT_REGIST = "not regist";
    public static final String RESULT_STATE_SERVER_ERROR = "server error";
    public static final String RESULT_STATE_CLIENT_ERROR = "client error";
    public static final String RESULT_DATA_MODIFYED = "data modifyed";
    public static final String RESULT_STATE_OK = "OK";

    
    private String appspot_hostname;
    private String appspot_ssl_url;
    private String tel;
    private String devId;
    private String simSerial;
    private boolean userStateIsChecked;
    private boolean userIsRegisted;
    private boolean networkEnabled;
    private Context mContext;
    private NetworkStatusDetector netstat;
    
    public CloudSyncronizer(Context context, String hostname, String ssl_url){
        mContext = context;
        appspot_hostname = hostname;
        appspot_ssl_url = ssl_url;
        // 端末情報をめっこりひっぱってくる
        TelephonyManager tm = (TelephonyManager) context.getSystemService(Context.TELEPHONY_SERVICE);
        tel = tm.getLine1Number();
        devId = tm.getDeviceId();
        simSerial = tm.getSimSerialNumber();
        userStateIsChecked = false;
        networkEnabled = false;
        
        netstat = NetworkStatusDetector.getInstance();
    }

    public boolean checkNetworkAndRegistlation(CloudTaskCallback checkCallback){
        if(netstat.networkIsEnabled(mContext)
                && netstat.canResolveDNS(appspot_hostname)
                && netstat.canReachByHTTP(appspot_ssl_url)){
            networkEnabled = true;
            UserCheckTask task = new UserCheckTask(checkCallback);
            task.execute(appspot_ssl_url + "/androiduser", tel, devId, simSerial);
            return true;
        } else {
            Toast.makeText(mContext, "ネットワークを確認してください", Toast.LENGTH_LONG).show();
            return false;
        }
    }
    
    /**
     * 1件登録する
     * @param params
     * @return
     * @throws NotRegistException 
     * @throws IOException 
     */
    public void updateToCloud(String pathAtServer, HashMap<String, String> params, CloudTaskCallback callback) throws NotRegistException, IOException{
        if(!networkEnabled){
            throw new IOException("ネットワークを確認してください.");
        }
        if(!userIsRegisted){
            throw new NotRegistException("try to regist before updateToCloud().");
        }
        
        PostToCloudTask task = new PostToCloudTask(params, callback);
        task.execute(appspot_ssl_url + pathAtServer, tel, devId, simSerial);
    }
    
    /**
     * 今cursorが指しているレコードについて、_id以外のカラムをparamsに詰めてupdateToCloud()を呼ぶ
     * cursorが1つ以上のレコードを含んでいる事は呼び出し側で確認すること。
     * @param pathAtServer
     * @param cursor
     * @param callback
     * @throws NotRegistException
     * @throws IOException
     */
    public void updateToCloud(String pathAtServer, Cursor cursor, CloudTaskCallback callback) throws NotRegistException, IOException{
        if(!networkEnabled){
            throw new IOException("ネットワークを確認してください.");
        }
        if(!userIsRegisted){
            throw new NotRegistException("try to regist before updateToCloud().");
        }
        if(cursor.getCount() == 0){
            return;
        }
        
        cursor.moveToFirst();
        // cursorの内容をHashMapに入れる
        HashMap<String, String> params = new HashMap<String, String>();
        int colCount = cursor.getColumnCount();
        if(colCount > 0){
            String colName;
            Date time;
            SimpleDateFormat sdf = new SimpleDateFormat("yyyy/MM/dd HH:mm:ss");
            for(int i = 0; i < colCount; i++){
                colName = cursor.getColumnName(i);
                if("created_at".equals(colName) || "updated_at".equals(colName)){
                    time = new Date(cursor.getLong(i));
                    params.put(colName, sdf.format(time));
                } else {
                    params.put(colName, cursor.getString(i));
                }
            }
            updateToCloud(pathAtServer, params, callback);
        }
    }


    public void deleteFromCloud(String pathAtServer, HashMap<String, String> params, CloudTaskCallback callback) throws NotRegistException, IOException{
        if(!networkEnabled){
            throw new IOException("ネットワークを確認してください.");
        }
        if(!userIsRegisted){
            throw new NotRegistException("try to regist before deleteFromCloud().");
        }
        if(null == params){
            params = new HashMap<String, String>();
        }
        params.put("_method", "delete");
        
        DeleteFromCloudTask task = new DeleteFromCloudTask(params, callback);
        task.execute(appspot_ssl_url + pathAtServer, tel, devId, simSerial);
    }

    /**
     * データの一覧を取得し
     * クライド側のタイムスタンプが新しければ、Android側のデータを更新する
     * @return
     * @throws NotRegistException 
     * @throws IOException 
     */
    public void syncFromCloud(String pathAtServer, GetableEntiryListPullParser pullParser, SyncFromCloudCallback syncCallback) throws NotRegistException, IOException{
        if(!networkEnabled){
            throw new IOException("ネットワークを確認してください.");
        }
        if(!userIsRegisted){
            throw new NotRegistException("try to regist before syncFromCloud().");
        }

        SyncFromCloudTask task = new SyncFromCloudTask(pullParser, syncCallback);
        task.execute(appspot_ssl_url + pathAtServer, tel, devId, simSerial);
    }
    
    public void executeUserRegistTask(CloudTaskCallback registCallback){
        UserRegistTask task = new UserRegistTask(registCallback);
        task.execute(appspot_ssl_url + "/androiduser", tel, devId, simSerial);
    }
    
    public interface CloudTaskCallback{
        void onPost(String result, Map<String, String> entity);
    }
    
    private class UserCheckTask extends AsyncTask<String, Integer, String> {
        private static final String TAG = "UserCheckTask";
        private CloudTaskCallback callback;
        private ResultPullParser pullParser;

        public UserCheckTask(CloudTaskCallback checkCallback){
            super();
            callback = checkCallback;
            pullParser = new ResultPullParser();
        }
        
        /**
         * UIスレッドでのプログレス表示用
         */
        @Override
        protected void onPreExecute() {
            
        }
        
        /**
         * バックグラウンドでのスレッド処理用
         * params[0] : サクセス先URL
         * params[1] : TEL番号
         * params[2] : デバイスID
         * params[3] : SIMシリアル番号
         */
        @Override
        protected String doInBackground(String... params) {
            Log.d(TAG, "enter doInBackground()");
            HashMap<String, String> query = new HashMap<String, String>();
            try {
                query.put("tel", params[1]);
                query.put("devid", params[2]);
                query.put("simserial", params[3]);
                RestfulClient.get(params[0], query, pullParser);
            } catch (HttpResponseException e){
                if(404 == e.getStatusCode()){
                    Log.d(TAG, "this android user is not found. try to regist.");
                    return RESULT_STATE_NOT_REGIST;
                } else {
                    Log.e(TAG, e.getMessage(), e);
                    return RESULT_STATE_SERVER_ERROR;
                }
            } catch (Exception e) {
                Log.e(TAG, e.getMessage(), e);
                return RESULT_STATE_CLIENT_ERROR;
            }
            if(pullParser.resultIsSuccess()){
                return RESULT_STATE_OK;
            } else {
                return RESULT_STATE_NOT_REGIST;
            }
        }
        
        /**
         * UIスレッドでの処理用
         */
        @Override
        protected void onPostExecute(String result) {
            Log.d(TAG, "enter onPostExecute() result: " + result);
            userStateIsChecked = true;
            if(RESULT_STATE_OK.equals(result)){
                userIsRegisted = true;
            } else {
                userIsRegisted = false;
            }
            
            if(null != callback){
                callback.onPost(String.valueOf(result), pullParser.getResult());
            }
        }
    }
    
    private class UserRegistTask extends AsyncTask<String, Integer, Boolean> {
        private static final String TAG = "UserRegistTask";
        private CloudTaskCallback callback;
        private ResultPullParser pullParser;

        public UserRegistTask(CloudTaskCallback registCallback){
            super();
            callback = registCallback;
            pullParser = new ResultPullParser();
        }
        
        /**
         * UIスレッドでのプログレス表示用
         */
        @Override
        protected void onPreExecute() {
            
        }
        
        /**
         * バックグラウンドでのスレッド処理用
         * params[0] : サクセス先URL
         * params[1] : TEL番号
         * params[2] : デバイスID
         * params[3] : SIMシリアル番号
         */
        @Override
        protected Boolean doInBackground(String... params) {
            Log.d(TAG, "enter doInBackground()");
            HashMap<String, String> query = new HashMap<String, String>();
            try {
                query.put("tel", params[1]);
                query.put("devid", params[2]);
                query.put("simserial", params[3]);
                RestfulClient.post(params[0], query, pullParser);
            } catch (HttpResponseException e){
                Log.e(TAG, e.getMessage(), e);
                return false;
            } catch (Exception e) {
                Log.e(TAG, e.getMessage(), e);
                return false;
            }
            return pullParser.resultIsSuccess();
        }
        
        /**
         * UIスレッドでの処理用
         */
        @Override
        protected void onPostExecute(Boolean result) {
            Log.d(TAG, "enter onPostExecute(). result:" + result);
            userStateIsChecked = true;
            userIsRegisted = result;
            
            if(null != callback){
                callback.onPost(String.valueOf(result), pullParser.getResult());
            }
        }
    }

    private class PostToCloudTask extends AsyncTask<String, Integer, String> {
        private static final String TAG = "PostToCloudTask";
        
        private HashMap<String, String> query;
        private CloudTaskCallback callback;
        private ResultPullParser pullParser;
        
        public PostToCloudTask(HashMap<String, String> postQuery, CloudTaskCallback postCallback){
            super();
            if(null == postQuery){
                query = null;
            } else {
                query = (HashMap<String, String>) postQuery.clone();
            }
            callback = postCallback;
            pullParser = new ResultPullParser();
        }
        
        /**
         * UIスレッドでのプログレス表示用
         */
        @Override
        protected void onPreExecute() {
            
        }
        
        /**
         * クラウド上のデータストア(python with kay)にデータを登録する
         * バックグラウンドでのスレッド処理用
         * params[0] : 登録先モデルを指すURL
         * params[1] : TEL番号
         * params[2] : デバイスID
         * params[3] : SIMシリアル番号
         */
        @Override
        protected String doInBackground(String... params) {
            Log.d(TAG, "enter doInBackground()");
            String targetUrl = params[0] + "?tel=" + params[1] + "&devid=" + params[2] + "&simserial=" + params[3];
            try {
                RestfulClient.post(targetUrl, query, pullParser);
            } catch (HttpResponseException e){
                if(404 == e.getStatusCode()){
                    Log.d(TAG, "this android user is not found. try to regist.");
                    return RESULT_STATE_NOT_REGIST;
                } else {
                    Log.e(TAG, e.getMessage(), e);
                    return RESULT_STATE_SERVER_ERROR;
                }
            } catch (Exception e) {
                Log.e(TAG, e.getMessage(), e);
                return RESULT_STATE_CLIENT_ERROR;
            }
            if(pullParser.resultIsSuccess()){
                return RESULT_STATE_OK;
            } else {
                return RESULT_STATE_NOT_REGIST;
            }
        }
        
        
        /**
         * UIスレッドでの処理用
         */
        @Override
        protected void onPostExecute(String result) {
            Log.d(TAG, "enter onPostExecute(). result:" + result);
            if(null != callback){
                callback.onPost(result, pullParser.getResult());
            }
        }
    }

    private class DeleteFromCloudTask extends AsyncTask<String, Integer, String> {
        private static final String TAG = "DeleteFromCloudTask";
        
        private HashMap<String, String> query;
        private CloudTaskCallback callback;
        private ResultPullParser pullParser;
        
        public DeleteFromCloudTask(HashMap<String, String> deleteQuery, CloudTaskCallback postCallback){
            super();
            if(null == deleteQuery){
                query = null;
            } else {
                query = (HashMap<String, String>) deleteQuery.clone();
            }
            callback = postCallback;
            pullParser = new ResultPullParser();
        }
        
        /**
         * UIスレッドでのプログレス表示用
         */
        @Override
        protected void onPreExecute() {
            
        }
        
        /**
         * クラウド上のデータストア(python with kay)にデータを登録する
         * バックグラウンドでのスレッド処理用
         * params[0] : 登録先モデルを指すURL
         * params[1] : TEL番号
         * params[2] : デバイスID
         * params[3] : SIMシリアル番号
         */
        @Override
        protected String doInBackground(String... params) {
            Log.d(TAG, "enter doInBackground()");
            String targetUrl = params[0] + "?tel=" + params[1] + "&devid=" + params[2] + "&simserial=" + params[3];
            try {
                RestfulClient.delete(targetUrl, query, pullParser);
            } catch (HttpResponseException e){
                if(404 == e.getStatusCode()){
                    Log.d(TAG, "this android user is not found. try to regist.");
                    return RESULT_STATE_NOT_REGIST;
                } else {
                    Log.e(TAG, e.getMessage(), e);
                    return RESULT_STATE_SERVER_ERROR;
                }
            } catch (Exception e) {
                Log.e(TAG, e.getMessage(), e);
                return RESULT_STATE_CLIENT_ERROR;
            }
            if(pullParser.resultIsSuccess()){
                return RESULT_STATE_OK;
            } else {
                return RESULT_DATA_MODIFYED;
            }
        }
        
        
        /**
         * UIスレッドでの処理用
         */
        @Override
        protected void onPostExecute(String result) {
            Log.d(TAG, "enter onPostExecute(). result:" + result);
            if(null != callback){
                callback.onPost(result, pullParser.getResult());
            }
        }
    }


    private class SyncFromCloudTask extends AsyncTask<String, Integer, List<Map<String, String>>> {
        private static final String TAG = "SyncFromCloudTask";
        
        private SyncFromCloudCallback callback;
        volatile private GetableEntiryListPullParser parser;
        
        public SyncFromCloudTask(GetableEntiryListPullParser pullParser, SyncFromCloudCallback syncCallback){
            super();
            callback = syncCallback;
            parser = pullParser;
        }
        
        /**
         * UIスレッドでのプログレス表示用
         */
        @Override
        protected void onPreExecute() {
            
        }
        
        /**
         * クラウド上のデータストア(python with kay)にデータを登録する
         * バックグラウンドでのスレッド処理用
         * params[0] : 登録先モデルを指すURL
         * params[1] : TEL番号
         * params[2] : デバイスID
         * params[3] : SIMシリアル番号
         */
        @Override
        protected List<Map<String, String>> doInBackground(String... params) {
            Log.d(TAG, "enter doInBackground()");
            List<Map<String, String>> dummy = new ArrayList<Map<String, String>>();
            String targetUrl = params[0] + "?tel=" + params[1] + "&devid=" + params[2] + "&simserial=" + params[3];
            try {
                RestfulClient.get(targetUrl, null, parser);
            } catch (HttpResponseException e){
                if(404 == e.getStatusCode()){
                    Log.d(TAG, "this android user is not found. try to regist.");
                    return dummy;
                } else {
                    Log.e(TAG, e.getMessage(), e);
                    return dummy;
                }
            } catch (Exception e) {
                Log.e(TAG, e.getMessage(), e);
                return dummy;
            }
            return parser.getResults();
        }
        
        /**
         * UIスレッドでの処理用
         */
        @Override
        protected void onPostExecute(List<Map<String, String>> results) {
            Log.d(TAG, "enter onPostExecute(). size of results:" + results.size());
            if(null != callback && results != null){
                callback.onPost(results);
            }
        }
    }

    public interface SyncFromCloudCallback{
        void onPost(List<Map<String, String>> results);
    }
    
    public interface GetableEntiryListPullParser extends CustomPullParser {
        List<Map<String, String>> getResults();
    }

    public class NotRegistException extends Exception{
        public NotRegistException(String string) {
            super(string);
        }
    }
}
