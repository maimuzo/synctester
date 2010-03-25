package info.androidapp.examples.synctester;

import java.io.IOException;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Map;

import info.androidapp.examples.synctester.storage.FavoriteCursorAdapter;
import info.androidapp.examples.synctester.storage.FavoriteDBDAO;
import info.androidapp.utils.cloud.CloudSyncronizer;
import info.androidapp.utils.cloud.EntityListPullParser;
import info.androidapp.utils.cloud.CloudSyncronizer.CloudTaskCallback;
import info.androidapp.utils.cloud.CloudSyncronizer.NotRegistException;
import info.androidapp.utils.cloud.CloudSyncronizer.SyncFromCloudCallback;
import android.app.Activity;
import android.content.ContentValues;
import android.database.Cursor;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.AdapterView;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.Toast;
import android.widget.AdapterView.OnItemClickListener;

public class SyncTestActivity extends Activity {
    private final static String TAG = "SyncTestActivity";
    private FavoriteDBDAO favoriteDAO;
    private EditText urlEdit;
    private EditText titleEdit;
    private ListView favoriteList;
    private FavoriteCursorAdapter favoriteAdapter;
    private CloudSyncronizer sync;
    private final static int MAX_RETRY = 3; 
    private int retryCounter;
    
    private static final String[] FAVORITE_CURSOR_COLUMNS = new String[] {
        FavoriteDBDAO.URL,
        FavoriteDBDAO.TITLE,
    };
    private static final int[] FAVORITE_BINDING_RESOURCES = new int[] {
        R.id.favorite_url_TextView_row,
        R.id.favorite_title_TextView_row,
    };

    
    /** Called when the activity is first created. */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.main);
        
        favoriteDAO = new FavoriteDBDAO(SyncTestActivity.this);
        String host = "maimuzo-py.appspot.com";
        String url = "https://" + host;
//        String host = "192.168.25.4";
//        String url = "http://192.168.25.4:8080";
        sync = new CloudSyncronizer(SyncTestActivity.this, host, url);
        
        urlEdit = (EditText) findViewById(R.id.url_edit);
        titleEdit = (EditText) findViewById(R.id.title_edit);
        findViewById(R.id.commit_button).setOnClickListener(new View.OnClickListener() {
            // commitボタンを押した時
            public void onClick(View v) {
                // URLとTITLEをDBに登録してからクラウドにリクエストを出す
                ContentValues values = new ContentValues();
                values.put("url", urlEdit.getText().toString());
                values.put("title", titleEdit.getText().toString());
                values.put(FavoriteDBDAO.WAS_UPDATED, 0);
                values.put(FavoriteDBDAO.WAS_DELETED, 0);
                long inserted_id = favoriteDAO.insert(values);
                urlEdit.setText("http://");
                titleEdit.setText("");
                retryCounter = 0;
                Cursor cursor = favoriteDAO.get(inserted_id);
                cursor.moveToFirst();
                try {
                    sync.updateToCloud("/favorite/" + inserted_id, cursor, updateCallback);
                } catch (Exception e) {
                    Log.e(TAG, e.getMessage(), e);
                } finally {
                    cursor.close();
                }
            }
        });

        
        favoriteList = (ListView) findViewById(R.id.favorite_list);
        favoriteList.setOnItemClickListener(new OnItemClickListener() {
            // リストのアイテムをタップしたとき
            public void onItemClick(AdapterView<?> parent, View view, int position, long id) {
                // 選択したレコードを論理削除
                // このカーソルはバインド中なので閉じれない
                Cursor cursor = (Cursor) favoriteAdapter.getItem(position);
                String recordId = cursor.getString(cursor.getColumnIndex(FavoriteDBDAO.ID));
                ContentValues values = new ContentValues();
                values.put(FavoriteDBDAO.WAS_UPDATED, 0);
                values.put(FavoriteDBDAO.WAS_DELETED, 1);
                favoriteDAO.update(values, FavoriteDBDAO.ID + " = " + recordId, null);
                retryCounter = 0;
                try {
                    sync.deleteFromCloud("/favorite/" + recordId, null, deleteCallback);
                } catch (Exception e) {
                    Log.e(TAG, e.getMessage(), e);
                }
            }
        });
        sync.checkNetworkAndRegistlation(checkCallback);
    }
    
    @Override
    public void onResume(){
        super.onResume();
        updateListView();
    }
    
    @Override
    public void onPause(){
        super.onPause();
        if(null != favoriteAdapter){
            favoriteAdapter.getCursor().close();
            favoriteAdapter = null;
        }
    }

    /**
     * Android端末が登録済みかどうかのチェック後に呼ばれる
     */
    private CloudTaskCallback checkCallback = new CloudTaskCallback() {
        public void onPost(String result, Map<String, String> entity) {
            if(result.equals(CloudSyncronizer.RESULT_STATE_OK)){
                try {
                    //　このAndroid端末が登録済みであれば、未更新レコードの確認と、クラウド側からの同期を行う
                    searchNeedToRequestRecord();
                } catch (Exception e) {
                    Log.e(TAG, e.getMessage(), e);
                }
            } else {
                // このAndroid端末が未登録なら登録する
                sync.executeUserRegistTask(registCallback);
            }
        }
    };

    /**
     * 新たにAndroid端末の登録を行った時に呼ばれる
     */
    private CloudTaskCallback registCallback = new CloudTaskCallback() {
        public void onPost(String result, Map<String, String> entity) {
            if("true".equals(result)){
                try {
                    Toast.makeText(SyncTestActivity.this, "Android端末を登録しました。", Toast.LENGTH_LONG).show();
                    //　このAndroid端末が登録済みであれば、未更新レコードの確認と、クラウド側からの同期を行う
                    searchNeedToRequestRecord();
                } catch (Exception e) {
                    Log.e(TAG, e.getMessage(), e);
                }
            } else {
                Toast.makeText(SyncTestActivity.this, "Android端末の登録に失敗しました。中止します。", Toast.LENGTH_LONG).show();
            }
        }
    };
    
    /**
     * 追加や更新時のリクエスト送信後に呼ばれる
     */
    private CloudTaskCallback updateCallback = new CloudTaskCallback() {
        /**
         * リクエスト送信後に呼び出される
         * @param result
         */
        public void onPost(String result, Map<String, String> entity) {
            if(result.equals(CloudSyncronizer.RESULT_STATE_OK)){
                // リクエスト成功なら、更新済みフラグをセットする
//                Log.d(TAG, entity.toString());
                String id = entity.get(FavoriteDBDAO.ID);
                Log.d(TAG, "updateCallback.id:" + id);
                ContentValues values = new ContentValues();
                values.put(FavoriteDBDAO.WAS_UPDATED, 1);
                favoriteDAO.update(values, FavoriteDBDAO.ID + " = " + id, null);
                // 未更新レコードがないか調べる
                searchNeedToRequestRecord();
            } else {
                Toast.makeText(SyncTestActivity.this, "更新リクエストが失敗しました。中止します。", Toast.LENGTH_LONG).show();
            }
        }
    };
    
    private CloudTaskCallback deleteCallback = new CloudTaskCallback() {
        public void onPost(String result, Map<String, String> entity) {
            if(result.equals(CloudSyncronizer.RESULT_STATE_OK) ||
                    result.equals(CloudSyncronizer.RESULT_DATA_MODIFYED)){
                // 削除成功なら、該当レコードを物理削除する
                // クラウド側にidが見つからないときも、SQLite内のデータは不要
                String id = entity.get(FavoriteDBDAO.ID);
                Log.d(TAG, "deleteCallback.id:" + id);
                favoriteDAO.delete(FavoriteDBDAO.ID + " = " + id, null);
                // 未更新レコードがないか調べる
                searchNeedToRequestRecord();
            } else {
                Toast.makeText(SyncTestActivity.this, "削除リクエストが失敗しました。中止します。", Toast.LENGTH_LONG).show();
            }
        }
    };
    
    private SyncFromCloudCallback syncCallback = new SyncFromCloudCallback() {
        public void onPost(List<Map<String, String>> entities) {
            String id;
            Map<String, String> foundEntity;
            ContentValues values;
            long updated_at, client_updated_at;
            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
            Date u;
            
            String sql = "SELECT * FROM " + FavoriteDBDAO.TABLE_NAME;
            Cursor cursor = favoriteDAO.rawQuery(sql, null);
            try{
                while(cursor.moveToNext()){
                    if(entities.size() == 0){
                        break;
                    }
                    id = cursor.getString(cursor.getColumnIndex(FavoriteDBDAO.ID));
                    Log.d(TAG, "syncCallback.cursor.id:" + id);
                    foundEntity = null;
                    // GAE側にあるものが、SQLite側にあるかどうか
                    for(Map<String, String> entity : entities){
                        if(id.equals(entity.get(FavoriteDBDAO.ID))){
                            foundEntity = entity;
                        }
                    }
                    if(foundEntity != null){
                        entities.remove(foundEntity);
                        Log.d(TAG, foundEntity.toString());
                        // GAE側にもSQLite側にもあるものは、updated_atを見て新しいければ追加する
                        updated_at = cursor.getLong(cursor.getColumnIndex(FavoriteDBDAO.UPDATED_AT));
                        // 解析失敗なら更新しない
                        client_updated_at = 0;
                        try {
                            client_updated_at = sdf.parse(foundEntity.get("client_updated_at")).getTime();
                        } catch (ParseException e) {
                            Log.e(TAG, e.getMessage(), e);
                        }
                        if(client_updated_at > updated_at){
                            values = packValues(foundEntity);
                            favoriteDAO.update(values, FavoriteDBDAO.ID + " = " + id, null);
                        }
                    }
                }
            } finally {
                cursor.close();
            }

            // 残ったentitiesはSQLite側に無いものなので、追加する
            for(Map<String, String> entity : entities){
                Log.d(TAG, "syncCallback.added.id:" + entity.get("_id"));
                values = packValues(entity);
                favoriteDAO.insert(values);
            }
            Toast.makeText(SyncTestActivity.this, "クラウドと同期しました。", Toast.LENGTH_LONG).show();
        }
    };
    
    private ContentValues packValues(Map<String, String> entity){
        ContentValues values = new ContentValues();
        values.put(FavoriteDBDAO.URL, entity.get(FavoriteDBDAO.URL));
        values.put(FavoriteDBDAO.TITLE, entity.get(FavoriteDBDAO.TITLE));
        values.put(FavoriteDBDAO.UPDATED_AT, entity.get("client_updated_at"));
        values.put(FavoriteDBDAO.WAS_UPDATED, 1);
        values.put(FavoriteDBDAO.WAS_DELETED, 0);
        return values;
    }

    private void  updateListView(){
        final String sql = "SELECT * FROM " + FavoriteDBDAO.TABLE_NAME
         + " WHERE WAS_DELETED != 1 ORDER BY UPDATED_AT DESC";
        Cursor cursor = favoriteDAO.rawQuery(sql, null);
        if(null == favoriteAdapter){
            favoriteAdapter =  new FavoriteCursorAdapter(SyncTestActivity.this,
                    R.layout.favorite_row, // Use a template
                    cursor, // Give the cursor to the list adatper
                    FAVORITE_CURSOR_COLUMNS, // Map the NAME column in the
                    FAVORITE_BINDING_RESOURCES // database to...
                );
            favoriteList.setAdapter(favoriteAdapter);
        } else {
            favoriteAdapter.changeCursor(cursor);
        }
    }
    
    /**
     * 登録されてないレコードがあれば、再度リクエストを出す。対象は最初のレコード
     */
    private void searchNeedToRequestRecord(){
        updateListView();
        if(retryCounter > MAX_RETRY){
            Toast.makeText(SyncTestActivity.this, "サーバへのリトライ回数が" + MAX_RETRY + "回を超えました。中止します。", Toast.LENGTH_LONG).show();
            return;
        } else {
            retryCounter++;
        }
        
        final String sql = "SELECT * FROM "+ FavoriteDBDAO.TABLE_NAME
         + " WHERE WAS_UPDATED = 0 ORDER BY UPDATED_AT DESC LIMIT 1";
        Cursor cursor = favoriteDAO.rawQuery(sql, null);
        try{
            if(cursor.getCount() > 0){
                cursor.moveToFirst();
                // 更新失敗しているものがあるなら、再度リクエストを発行する
                try {
                    int was_deleted = cursor.getInt(cursor.getColumnIndex(FavoriteDBDAO.WAS_DELETED));
                    String recordId = cursor.getString(cursor.getColumnIndex(FavoriteDBDAO.ID));
                    if(was_deleted == 1){
                        sync.deleteFromCloud("/favorite/" + recordId, null, deleteCallback);
                    } else {
                        sync.updateToCloud("/favorite/" + recordId, cursor, updateCallback);
                    }
                } catch (Exception e) {
                    Log.e(TAG, e.getMessage(), e);
                }
            } else {
                // すべて更新済みならクラウド側から同期させる
                try {
                    sync.syncFromCloud("/favorites", new EntityListPullParser(), syncCallback);
                } catch (Exception e) {
                    Log.e(TAG, e.getMessage(), e);
                }
            }
        } finally {
            cursor.close();
        }
    }
}