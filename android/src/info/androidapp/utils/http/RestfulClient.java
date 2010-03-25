package info.androidapp.utils.http;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.parsers.SAXParser;
import javax.xml.parsers.SAXParserFactory;

import org.apache.http.HttpEntity;
import org.apache.http.HttpResponse;
import org.apache.http.HttpStatus;
import org.apache.http.NameValuePair;
import org.apache.http.auth.AuthScope;
import org.apache.http.auth.UsernamePasswordCredentials;
import org.apache.http.client.ClientProtocolException;
import org.apache.http.client.HttpResponseException;
import org.apache.http.client.entity.UrlEncodedFormEntity;
import org.apache.http.client.methods.HttpDelete;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.client.methods.HttpPut;
import org.apache.http.client.methods.HttpUriRequest;
import org.apache.http.impl.client.DefaultHttpClient;
import org.apache.http.message.BasicNameValuePair;
import org.apache.http.protocol.HTTP;
import org.apache.http.util.EntityUtils;
import org.w3c.dom.Document;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;
import org.xml.sax.helpers.DefaultHandler;
import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserException;
import org.xmlpull.v1.XmlPullParserFactory;

import android.util.Log;

public class RestfulClient {
    private static final String TAG = "Restful";
    protected static String sBasicAuthUsername = "";
    protected static String sBasicAuthPassword = "";
    
    public static void setBasicAuth(String userName, String password){
        sBasicAuthUsername = userName;
        sBasicAuthPassword = password;
    }
    
    public static boolean basicAuthIsEnabled(){
        return !sBasicAuthUsername.equals("");
    }

	public static String get(String uri, HashMap<String,String> params) throws ClientProtocolException, IOException {
		String fulluri;

		if(null == params){
			fulluri = uri;
		} else {
		    if(hasQueryString(uri)){
	            fulluri = uri + "&" + packQueryString(params);
		    } else {
	            fulluri = uri + "?" + packQueryString(params);
		    }
		}
		
		HttpGet method = new HttpGet(fulluri);
		return EntityUtils.toString(doRequest(method));
	}

	public static Document get(String uri, HashMap<String,String> params, DocumentBuilder builder) throws ClientProtocolException, IOException, SAXException {
		String fulluri;

		if(null == params){
			fulluri = uri;
		} else {
            if(hasQueryString(uri)){
                fulluri = uri + "&" + packQueryString(params);
            } else {
                fulluri = uri + "?" + packQueryString(params);
            }
		}
		
		HttpGet method = new HttpGet(fulluri);
		return getDOM(doRequest(method), builder);
	}
	
    public static void get(String uri, HashMap<String,String> params, DefaultHandler handler) throws ClientProtocolException, IOException, SAXException, IllegalStateException, ParserConfigurationException {
        String fulluri;

        if(null == params){
            fulluri = uri;
        } else {
            if(hasQueryString(uri)){
                fulluri = uri + "&" + packQueryString(params);
            } else {
                fulluri = uri + "?" + packQueryString(params);
            }
        }
        
        HttpGet method = new HttpGet(fulluri);
        parseBySAX(doRequest(method), handler);
    }

    public static void get(String uri, HashMap<String,String> params, CustomPullParser pullParser) throws ClientProtocolException, IOException, SAXException, IllegalStateException, ParserConfigurationException {
        String fulluri;

        if(null == params){
            fulluri = uri;
        } else {
            if(hasQueryString(uri)){
                fulluri = uri + "&" + packQueryString(params);
            } else {
                fulluri = uri + "?" + packQueryString(params);
            }
        }
        
        HttpGet method = new HttpGet(fulluri);
        parseByPullParser(doRequest(method), pullParser);
    }

    public static String post(String uri, HashMap<String,String> params) throws ClientProtocolException, IOException {
		HttpPost method = new HttpPost(uri);
		if(null != params){
			List<NameValuePair> paramList = packEntryParams(params);
			method.setEntity(new UrlEncodedFormEntity(paramList, HTTP.UTF_8));
		}
		return EntityUtils.toString(doRequest(method));
	}

	public static Document post(String uri, HashMap<String,String> params, DocumentBuilder builder) throws ClientProtocolException, IOException, SAXException {
		HttpPost method = new HttpPost(uri);
		if(null != params){
			List<NameValuePair> paramList = packEntryParams(params);
			method.setEntity(new UrlEncodedFormEntity(paramList, HTTP.UTF_8));
		}
		return getDOM(doRequest(method), builder);
	}

    public static void post(String uri, HashMap<String,String> params, DefaultHandler handler) throws ClientProtocolException, IOException, SAXException, IllegalStateException, ParserConfigurationException {
        HttpPost method = new HttpPost(uri);
        if(null != params){
            List<NameValuePair> paramList = packEntryParams(params);
            method.setEntity(new UrlEncodedFormEntity(paramList, HTTP.UTF_8));
        }
        parseBySAX(doRequest(method), handler);
    }
	
    public static void post(String uri, HashMap<String,String> params, CustomPullParser pullParser) throws ClientProtocolException, IOException, SAXException, IllegalStateException, ParserConfigurationException {
        HttpPost method = new HttpPost(uri);
        if(null != params){
            List<NameValuePair> paramList = packEntryParams(params);
            method.setEntity(new UrlEncodedFormEntity(paramList, HTTP.UTF_8));
        }
        parseByPullParser(doRequest(method), pullParser);
    }

    public static String put(String uri, HashMap<String,String> params) throws ClientProtocolException, IOException {
		HttpPut method = new HttpPut(uri);
		if(null != params){
			List<NameValuePair> paramList = packEntryParams(params);
			method.setEntity(new UrlEncodedFormEntity(paramList, HTTP.UTF_8));
		}
		return EntityUtils.toString(doRequest(method));
	}

	public static Document put(String uri, HashMap<String,String> params, DocumentBuilder builder) throws ClientProtocolException, IOException, SAXException {
		HttpPut method = new HttpPut(uri);
		if(null != params){
			List<NameValuePair> paramList = packEntryParams(params);
			method.setEntity(new UrlEncodedFormEntity(paramList, HTTP.UTF_8));
		}
		return getDOM(doRequest(method), builder);
	}

    public static void put(String uri, HashMap<String,String> params, DefaultHandler handler) throws ClientProtocolException, IOException, SAXException, IllegalStateException, ParserConfigurationException {
        HttpPut method = new HttpPut(uri);
        if(null != params){
            List<NameValuePair> paramList = packEntryParams(params);
            method.setEntity(new UrlEncodedFormEntity(paramList, HTTP.UTF_8));
        }
        parseBySAX(doRequest(method), handler);
    }

    public static void put(String uri, HashMap<String,String> params, CustomPullParser pullParser) throws ClientProtocolException, IOException, SAXException, IllegalStateException, ParserConfigurationException {
        HttpPut method = new HttpPut(uri);
        if(null != params){
            List<NameValuePair> paramList = packEntryParams(params);
            method.setEntity(new UrlEncodedFormEntity(paramList, HTTP.UTF_8));
        }
        parseByPullParser(doRequest(method), pullParser);
    }

    public static String delete(String uri, HashMap<String,String> params) throws ClientProtocolException, IOException {
		String fulluri;

		if(null == params){
			fulluri = uri;
		} else {
            if(hasQueryString(uri)){
                fulluri = uri + "&" + packQueryString(params);
            } else {
                fulluri = uri + "?" + packQueryString(params);
            }
		}
		
		HttpDelete method = new HttpDelete(fulluri);
		return EntityUtils.toString(doRequest(method));
	}

	public static Document delete(String uri, HashMap<String,String> params, DocumentBuilder builder) throws ClientProtocolException, IOException, SAXException {
		String fulluri;

		if(null == params){
			fulluri = uri;
		} else {
            if(hasQueryString(uri)){
                fulluri = uri + "&" + packQueryString(params);
            } else {
                fulluri = uri + "?" + packQueryString(params);
            }
		}
		
		HttpDelete method = new HttpDelete(fulluri);
		return getDOM(doRequest(method), builder);
	}
	
    public static void delete(String uri, HashMap<String,String> params, DefaultHandler handler) throws ClientProtocolException, IOException, SAXException, IllegalStateException, ParserConfigurationException {
        String fulluri;

        if(null == params){
            fulluri = uri;
        } else {
            if(hasQueryString(uri)){
                fulluri = uri + "&" + packQueryString(params);
            } else {
                fulluri = uri + "?" + packQueryString(params);
            }
        }
        
        HttpDelete method = new HttpDelete(fulluri);
        parseBySAX(doRequest(method), handler);
    }

    public static void delete(String uri, HashMap<String,String> params, CustomPullParser pullParser) throws ClientProtocolException, IOException, SAXException, IllegalStateException, ParserConfigurationException {
        String fulluri;

        if(null == params){
            fulluri = uri;
        } else {
            if(hasQueryString(uri)){
                fulluri = uri + "&" + packQueryString(params);
            } else {
                fulluri = uri + "?" + packQueryString(params);
            }
        }
        
        HttpDelete method = new HttpDelete(fulluri);
        parseByPullParser(doRequest(method), pullParser);
    }

    /*
	 * DocumentBuilderFactory.newInstance()
	 * 	.setValidating(true)
	 * 	.setIgnoringElementContentWhitespace(true)
	 * 	.newDocumentBuilder()
	 *  .parse(hoge);
	 *  でうまく空ノードを取ってくれそうだけど、バリデータが実装されてないのか例外が出る。
	 *  また
	 *  Node.normalize()もなんか変
	 *  なので、自前で改行やスペースだけのテキストノードを削除する。
	 */
    public static Node removeEmptyNodes(Node currentNode) {
        NodeList list = currentNode.getChildNodes();
        int n = list.getLength();
        if(0 < n){
            for (int i = 0; i < n; i++) {
                Node childNode = list.item(i);
                String value = childNode.getNodeValue();
                // Log.v(TAG, "value : " + value);
                if(Node.TEXT_NODE == childNode.getNodeType() && value.trim().equals("")){
                	// Log.v(TAG, "remove " + Integer.toString(i) + "th node of " + currentNode.getNodeName());
                	currentNode.removeChild(childNode);
                }else{
                	removeEmptyNodes(childNode);
                }
            }
        }
        return currentNode;
    }

	
	protected static HttpEntity doRequest(HttpUriRequest method) throws ClientProtocolException, IOException {
		DefaultHttpClient client = new DefaultHttpClient();
		
		// BASIC認証用のユーザ名が設定されていれば、BASIC認証を行う
		if(basicAuthIsEnabled()){
			URI uri = method.getURI();
			client.getCredentialsProvider().setCredentials(
				new AuthScope(uri.getHost(), uri.getPort()),
				new UsernamePasswordCredentials(sBasicAuthUsername, sBasicAuthPassword));
		}
		HttpResponse response = null;
		
		try {
			response = client.execute(method);
			int statuscode = response.getStatusLine().getStatusCode();
			
			//リクエストが成功 200 OK and 201 CREATED
			if (statuscode == HttpStatus.SC_OK | statuscode == HttpStatus.SC_CREATED){ 
				return response.getEntity();
			} else {
			    String html = EntityUtils.toString(response.getEntity());
				throw new HttpResponseException(statuscode, "Response code is " + Integer.toString(statuscode) + ". message:" + html);
			}
		}catch (RuntimeException e) {
			method.abort();
			Log.v(TAG, e.getMessage());
			throw new RuntimeException(e);
		}
	}
	
	protected static List<NameValuePair> packEntryParams(HashMap<String,String> map){
		if(null == map){
			throw new RuntimeException("map is null");
		}

		List<NameValuePair> paramList = new ArrayList<NameValuePair>();
		Iterator<Map.Entry<String, String>> itr = map.entrySet().iterator();
		Map.Entry<String, String> entry;
		
		while(itr.hasNext()){
			entry = itr.next();
			paramList.add(new BasicNameValuePair(entry.getKey(), entry.getValue()));
		}
		return paramList;
	}
	
	protected static boolean hasQueryString(String uri){
        URI u;
        try {
            u = new URI(uri);
            if(u.getQuery() == null){
                return false;
            } else {
                return true;
            }
        } catch (URISyntaxException e) {
            Log.e(TAG, e.getMessage(), e);
            return false;
        }
	}
	
	protected static String packQueryString(HashMap<String,String> map) throws UnsupportedEncodingException{
		if(null == map){
			throw new RuntimeException("map is null");
		}
		
		StringBuilder sb = new StringBuilder(100);
		Iterator<Map.Entry<String, String>> itr = map.entrySet().iterator();
		Map.Entry<String, String> entry;
		
		while(itr.hasNext()){
			entry = itr.next();
			if(0 != sb.length()){
				sb.append("&");
			}
			sb.append(URLEncoder.encode(entry.getKey(), "UTF-8"));
			sb.append("=");
			sb.append(URLEncoder.encode(entry.getValue(), "UTF-8"));
		}
		return sb.toString();
	}
	
	protected static Document getDOM(HttpEntity entity, DocumentBuilder builder) throws IOException, SAXException{
		BufferedInputStream is = new BufferedInputStream(entity.getContent());
		Document doc = null;
		try {
			doc = builder.parse(is);
			return doc;
		} finally{
			is.close();
		}
	}
	
    protected static void parseBySAX(HttpEntity entity, DefaultHandler handler) throws ParserConfigurationException, IllegalStateException, IOException, SAXException{
        BufferedInputStream is = new BufferedInputStream(entity.getContent());
        try {
            SAXParserFactory saxParserFactory = SAXParserFactory.newInstance();
            SAXParser saxParser = saxParserFactory.newSAXParser();
            saxParser.parse(is, handler);
        } finally{
            is.close();
        }
    }
    
    protected static void parseByPullParser(HttpEntity entity, CustomPullParser pullParser) throws ParserConfigurationException, IllegalStateException, IOException, SAXException{
        BufferedInputStream is = new BufferedInputStream(entity.getContent());
        try {
            pullParser.parseByPullParser(is);
        } finally{
            is.close();
        }
    }

    public interface CustomPullParser {
        void parseByPullParser(BufferedInputStream is);
    }

    /**
     * Example of CustomPullParser
     * 
    public class ExampleCustomPullParser implements CustomPullParser{
        public void parseByPullParser(BufferedInputStream is){
            XmlPullParserFactory factory;
            try {
                factory = XmlPullParserFactory.newInstance();
                XmlPullParser xpp = factory.newPullParser();
                xpp.setInput(is, "UTF-8");
                int eventType = xpp.getEventType();
                while (eventType != XmlPullParser.END_DOCUMENT) {
                    if (eventType == XmlPullParser.START_DOCUMENT) {
                        System.out.println("Start document");
                    } else if (eventType == XmlPullParser.END_DOCUMENT) {
                        System.out.println("End document");
                    } else if (eventType == XmlPullParser.START_TAG) {
                        System.out.println("Start tag " + xpp.getName());
                    } else if (eventType == XmlPullParser.END_TAG) {
                        System.out.println("End tag " + xpp.getName());
                    } else if (eventType == XmlPullParser.TEXT) {
                        System.out.println("Text " + xpp.getText());
                    }
                    eventType = xpp.next();
                }
            } catch (XmlPullParserException e) {
                // TODO Auto-generated catch block
                e.printStackTrace();
            } catch (IOException e) {
                // TODO Auto-generated catch block
                e.printStackTrace();
            }
        }
    }
    */

}
