package info.androidapp.examples.synctester.storage;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.util.Log;

public class DatabaseHelper extends SQLiteOpenHelper {
    private static final String TAG = "DatabaseHelper";
    private static final String DATABASE_NAME = "synctest.db";
    private static final int DATABASE_VERSION = 1;
    
    private static final String favoritesSql =
         "CREATE TABLE " + FavoriteDBDAO.TABLE_NAME + " ("
        + FavoriteDBDAO.ID + " INTEGER PRIMARY KEY,"
        + FavoriteDBDAO.URL + " TEXT,"
        + FavoriteDBDAO.TITLE + " TEXT,"
        + FavoriteDBDAO.WAS_UPDATED + " BOOLEAN,"
        + FavoriteDBDAO.WAS_DELETED + " BOOLEAN,"
        + FavoriteDBDAO.CREATED_AT + " INTEGER,"
        + FavoriteDBDAO.UPDATED_AT + " INTEGER"
        + ");";
    
    
    DatabaseHelper(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        updateToVersion1(db);
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        Log.w(TAG, "Upgrading database from version " + oldVersion + " to "
                + newVersion + ", which will destroy all old data");
    }
    
    private void updateToVersion1(SQLiteDatabase db){
        db.execSQL(favoritesSql);

        String addIndexSql;
        addIndexSql = "create index " + FavoriteDBDAO.TABLE_NAME + "_" + FavoriteDBDAO.ID + "_index on " + FavoriteDBDAO.TABLE_NAME + "(" + FavoriteDBDAO.ID + ");";
        db.execSQL(addIndexSql);
        addIndexSql = "create index " + FavoriteDBDAO.TABLE_NAME + "_" + FavoriteDBDAO.WAS_UPDATED + "_index on " + FavoriteDBDAO.TABLE_NAME + "(" + FavoriteDBDAO.WAS_UPDATED + ");";
        db.execSQL(addIndexSql);

    }

}
