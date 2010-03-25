package info.androidapp.examples.synctester.storage;

import android.content.Context;
import android.database.Cursor;
import android.text.format.DateFormat;
import android.util.Log;
import android.view.View;
import android.widget.SimpleCursorAdapter;
import android.widget.TextView;

public class FavoriteCursorAdapter extends SimpleCursorAdapter {
    
    private boolean debugMode;

    public FavoriteCursorAdapter(Context context, int layout, Cursor c,
            String[] from, int[] to) {
        super(context, layout, c, from, to);
        setViewBinder(new ViewBinderForRoom());
        debugMode = false;
    }
    
    public void setDebugMode(boolean flag){
        debugMode = flag;
    }

    public class ViewBinderForRoom implements SimpleCursorAdapter.ViewBinder {
        private final static String TAG = "ViewBinderForFavorite";

        /**
         * see http://www.narazaki.info/2009/08/simplecursoradapter.html
         */
        public boolean setViewValue(View view, Cursor cursor, int columnIndex) {
            if(debugMode){
                Log.d(TAG, "columnIndex: " + columnIndex);
            }
            String currentColumnName = cursor.getColumnName(columnIndex);
            if(currentColumnName.equals(FavoriteDBDAO.URL)
                || currentColumnName.equals(FavoriteDBDAO.TITLE) ){
                String s = cursor.getString(columnIndex);
                TextView text_view = (TextView) view;
                text_view.setText(s);
                return true;
            }
            return false;
        }
        
        private void setDateAndTimePair(Cursor cursor, View view, int timeColumnIndex, String dateColumnName){
            long timeValue = cursor.getLong(timeColumnIndex);
            long dateValue = cursor.getLong(cursor.getColumnIndex(dateColumnName));
            TextView text_view = (TextView) view;
            text_view.setText(DateFormat.format("MM/dd ", dateValue).toString() + DateFormat.format("k:mm", timeValue).toString());
        }
    }
    
}
