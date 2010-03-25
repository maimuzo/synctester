package info.androidapp.examples.synctester.storage;


import java.util.Date;
import java.util.HashMap;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.database.sqlite.SQLiteQueryBuilder;
import android.text.TextUtils;
import android.util.Log;

public class FavoriteDBDAO {

    private static final String TAG = "FavoriteDBDAO";

    public static final String TABLE_NAME = "favorites";
    
    public static final String ID = "_id";
    public static final String URL = "url";
    public static final String TITLE = "title";
    public static final String WAS_UPDATED = "was_updated"; // flag for "updated" or "still"
    public static final String WAS_DELETED = "was_deleted"; // for logical delete
    public static final String CREATED_AT = "created_at";
    public static final String UPDATED_AT = "updated_at";
    public static final String ALL_COLUMNS = "*";
    
    private static HashMap<String, String> sProjectionMap;



    private DatabaseHelper mOpenHelper;

    public FavoriteDBDAO(Context context) {
        mOpenHelper = new DatabaseHelper(context);
    }

    public Cursor query(String[] projection, String selection, String[] selectionArgs,
            String sortOrder) {
        SQLiteQueryBuilder qb = new SQLiteQueryBuilder();

        qb.setTables(TABLE_NAME);
        qb.setProjectionMap(sProjectionMap);

        String orderBy;
        if (TextUtils.isEmpty(sortOrder)) {
            orderBy = UPDATED_AT;
        } else {
            orderBy = sortOrder;
        }

        // Get the database and run the query
        SQLiteDatabase db = mOpenHelper.getReadableDatabase();
        Cursor c = qb.query(db, projection, selection, selectionArgs, null, null, orderBy);
        return c;
    }
    
    public Cursor rawQuery(String sql, String[] selectionArgs){
        SQLiteDatabase db = mOpenHelper.getReadableDatabase();
        return db.rawQuery(sql, selectionArgs);
    }
    
    public Cursor get(long id){
        String sql = "SELECT " + FavoriteDBDAO.ALL_COLUMNS + " FROM " + FavoriteDBDAO.TABLE_NAME
         + " WHERE _id = " + id;
        return rawQuery(sql, null);
    }


    public long insert(ContentValues values) {
        Long now = new Date().getTime();

        if (values.containsKey(CREATED_AT) == false) {
            values.put(CREATED_AT, now);
        }

        if (values.containsKey(UPDATED_AT) == false) {
            values.put(UPDATED_AT, now);
        }

        SQLiteDatabase db = mOpenHelper.getWritableDatabase();
        return db.insert(TABLE_NAME, "", values);
    }

    public int delete(String where, String[] whereArgs) {
        SQLiteDatabase db = mOpenHelper.getWritableDatabase();
        int count;
        count = db.delete(TABLE_NAME, where, whereArgs);
        return count;
    }

    public int update(ContentValues values, String where, String[] whereArgs) {
        SQLiteDatabase db = mOpenHelper.getWritableDatabase();
        int count;
        values.put(UPDATED_AT, new Date().getTime());

        count = db.update(TABLE_NAME, values, where, whereArgs);
        return count;
    }
        
    
    static {
        sProjectionMap = new HashMap<String, String>();
        sProjectionMap.put(ID, ID);
        sProjectionMap.put(URL, URL);
        sProjectionMap.put(TITLE, TITLE);
        sProjectionMap.put(WAS_UPDATED, WAS_UPDATED);
        sProjectionMap.put(WAS_DELETED, WAS_DELETED);
        sProjectionMap.put(CREATED_AT, CREATED_AT);
        sProjectionMap.put(UPDATED_AT, UPDATED_AT);
    }

}
