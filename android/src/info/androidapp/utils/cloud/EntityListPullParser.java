package info.androidapp.utils.cloud;

import info.androidapp.utils.cloud.CloudSyncronizer.GetableEntiryListPullParser;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserException;
import org.xmlpull.v1.XmlPullParserFactory;

import android.util.Log;


public class EntityListPullParser implements GetableEntiryListPullParser{
    private static final String TAG = "EntityListPullParser";
    private List<Map<String, String>> results;
    private boolean inItem;
    
    public EntityListPullParser(){
        results = new ArrayList<Map<String, String>>();
        inItem = false;
    }
    
    public void parseByPullParser(BufferedInputStream is){
        XmlPullParserFactory factory;
        HashMap<String, String> holder = new HashMap<String, String>();
        String currentTag = "", currentText = "";
        try {
            factory = XmlPullParserFactory.newInstance();
            XmlPullParser xpp = factory.newPullParser();
            xpp.setInput(is, "UTF-8");
            
            int eventType = xpp.getEventType();
            while (eventType != XmlPullParser.END_DOCUMENT) {                                                                                           
                if (eventType == XmlPullParser.START_TAG) {
                    String tag = xpp.getName();
                    if("entity".equals(tag)){
                        holder = new HashMap<String, String>();
                        inItem = true;
                    } else if(inItem){
                        currentTag = tag;
                    }
                } else if (eventType == XmlPullParser.END_TAG) {
                    String tag = xpp.getName();
                    if("entity".equals(tag)){
                        results.add(holder);
                        inItem = false;
                    } else if(inItem){
                        holder.put(currentTag, currentText);
                    }
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
    
    public List<Map<String, String>> getResults(){
        return results;
    }
}
