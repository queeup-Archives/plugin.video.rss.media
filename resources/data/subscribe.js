/*
 * Javascript for plugin.video.rss.media
 */

var rss_url = encodeURIComponent(location.href);

if(window.XMLHttpRequest){ // Firefox
    request = new XMLHttpRequest();
}
else if(window.ActiveXObject){ // Internet Explorer
    request = new ActiveXObject("Microsoft.XMLHTTP");
}
else { // Your browser does not support XMLHTTPRequest
    alert("Your browser does not support XMLHTTPRequest objects...");
}
console.log("Adding RSS to XBMC RSS Add-on: " + location.href);
//alert('Adding RSS to XBMC RSS Add-on: ' + rss_url);

request.open("POST", "http://" + xbmc_address + ":" + xbmc_port + "/jsonrpc", false);
var data = '{"jsonrpc":"2.0", "method":"Player.Open", "params":{"item":{"file":"plugin://plugin.video.rss.media/?action=subscribe&url=' + rss_url + '" }}, "id" : 1}';
request.send(data);

/*
if (request.status === 200) {
console.log(request.responseText);
}
else {
console.log(request.status);
}
*/
