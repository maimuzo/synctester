package info.androidapp.utils.cloud;

import info.androidapp.utils.http.RestfulClient.CustomPullParser;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.util.HashMap;

import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserException;
import org.xmlpull.v1.XmlPullParserFactory;

import android.util.Log;


public class EntityPullParser implements CustomPullParser{
    private static final String TAG = "EntityPullParser";
    protected HashMap<String, String> result;
    
    public EntityPullParser(){
        result = new HashMap<String, String>();
    }
    
    public void parseByPullParser(BufferedInputStream is){
        XmlPullParserFactory factory;
        String currentTag = "", currentText = "";
        try {
            factory = XmlPullParserFactory.newInstance();
            XmlPullParser xpp = factory.newPullParser();
            xpp.setInput(is, "UTF-8");
            
            int eventType = xpp.getEventType();
            while (eventType != XmlPullParser.END_DOCUMENT) {                                                                                           
                if (eventType == XmlPullParser.START_TAG) {
                    currentTag = xpp.getName();
                } else if (eventType == XmlPullParser.END_TAG) {
                    result.put(currentTag, currentText);
                } else if (eventType == XmlPullParser.TEXT) {
                    currentText = xpp.getText();
                }
                eventType = xpp.next();
            }
        } catch (XmlPullParserException e) {
            Log.e(TAG, e.getMessage(), e);
        } catch (IOException e) {
            Log.e(TAG, e.getMessage(), e);
        }
    }
    
    public HashMap<String, String> getResult(){
        return result;
    }
    
    public String getValue(String key){
        return result.get(key);
    }
}
