package info.androidapp.utils.cloud;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;

import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserException;
import org.xmlpull.v1.XmlPullParserFactory;

import android.util.Log;


public class ResultPullParser extends EntityPullParser{
    private static final String TAG = "ResultPullParser";
    
    public ResultPullParser(){
        super();
    }

    public boolean resultIsSuccess(){
        if("OK".equals(result.get("state"))){
            return true;
        } else {
            return false;
        }
    }

    public String getMessage(){
        return result.get("message");
    }
}
