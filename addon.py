# -*- coding: utf-8 -*-

# Imports
import os
import re
import sys
import time
import errno
import shelve
import shutil
import hashlib
import tempfile
import urllib
import urllib2
import feedparser
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# DEBUG
DEBUG = True

__addon__ = xbmcaddon.Addon()
__plugin__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__icon__ = __addon__.getAddonInfo('icon')
__path__ = __addon__.getAddonInfo('path')
__cachedir__ = __addon__.getAddonInfo('profile')
__language__ = __addon__.getLocalizedString
__settings__ = __addon__.getSetting

CACHE_1MINUTE = 60
CACHE_1HOUR = 3600
CACHE_1DAY = 86400
CACHE_1WEEK = 604800
CACHE_1MONTH = 2592000

CACHE_TIME = CACHE_1HOUR

# On windows profile folder not created automatically
if not os.path.exists(xbmc.translatePath(__cachedir__)):
  if DEBUG:
    print 'Profile folder not exist. Creating now for database!'
  os.mkdir(xbmc.translatePath(__cachedir__))

# Our database
db = shelve.open(xbmc.translatePath(__cachedir__ + 'rss.db'), protocol=2)


class Main:
  def __init__(self):
    if ("action=getfeed" in sys.argv[2]):
      self.get_feed(self.arguments('url', True))
    elif ("action=subscribe" in sys.argv[2]):
      self._subscribe()
    elif ("action=unsubscribe" in sys.argv[2]):
      self._unsubscribe(self.arguments('id', False))
    elif ("action=mysubscription" in sys.argv[2]):
      self.get_subscriptions()
    else:
      self.main_menu()

  def main_menu(self):
    if DEBUG:
      self.log('main_menu()')
    category = []
    # If keys exist in miro.db show My Subscription directory.
    if db.keys() != list():
      if DEBUG:
        self.log('My Subscriptions directory activated.')
      category += [{'title':__language__(30201), 'action':'mysubscriptions'}, ]
    db.close()
    category += [{'title':__language__(30202), 'action':'subscribe'}]
    for i in category:
      listitem = xbmcgui.ListItem(i['title'], iconImage='DefaultFolder.png', thumbnailImage=__icon__)
      parameters = '%s?action=%s' % (sys.argv[0], i['action'])
      xbmcplugin.addDirectoryItems(int(sys.argv[1]), [(parameters, listitem, True)])
    # Sort methods and content type...
    xbmcplugin.addSortMethod(handle=int(sys.argv[1]), sortMethod=xbmcplugin.SORT_METHOD_NONE)
    # End of directory...
    xbmcplugin.endOfDirectory(int(sys.argv[1]), True)

  def get_subscriptions(self):
    if DEBUG:
      self.log('get_subscriptions()')
    for k, v in db.iteritems():
      _id = k
      name = v['name']
      feedUrl = v['url']
      if not feedUrl:
        continue
      try:
        thumb = v['thumbnail']
      except:
        pass
      summary = v['description']
      listitem = xbmcgui.ListItem(name, iconImage='DefaultVideo.png', thumbnailImage=thumb)
      listitem.setInfo(type='video',
                       infoLabels={'title': name,
                                   'plot': summary})
      contextmenu = [(__language__(30102), 'XBMC.RunPlugin(%s?action=unsubscribe&id=%s)' % \
                                                          (sys.argv[0], _id))]
      listitem.addContextMenuItems(contextmenu, replaceItems=False)
      parameters = '%s?action=getfeed&url=%s' % (sys.argv[0], urllib.quote_plus(feedUrl))
      xbmcplugin.addDirectoryItems(int(sys.argv[1]), [(parameters, listitem, True)])
    db.close()
    # Sort methods and content type...
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_TITLE)
    # End of directory...
    xbmcplugin.endOfDirectory(int(sys.argv[1]), True)

  def get_feed(self, url):
    if DEBUG:
      self.log('get_feed()')
    feedHtml = fetcher.fetch(url)
    encoding = re.search(r"encoding=([\"'])([^\1]*?)\1", feedHtml).group(2)
    feedHtml = feedHtml.decode(encoding, 'ignore').encode('utf-8')

    feed = feedparser.parse(feedHtml)
    if 'items' in feed:
      items = feed['items']
    else:
      items = feed['entries']
    hasInvalidItems = False
    for item in items:
      infoLabels = {}
      infoLabels['duration'] = ''
      title = infoLabels['title'] = self._strip_tags(item.title.replace('&#39;', "'").replace('&amp;', '&'))
      if isinstance(title, str):  # BAD: Not true for Unicode strings!
        try:
          title = infoLabels['title'] = title.encode('utf-8', 'replace')  # .encode('utf-8')
        except:
          continue  # skip this, it likely will bork
      try:
        date_p = item.date_parsed
        infoLabels['date'] = time.strftime("%d.%m.%Y", date_p)
        #date = item.updated
      except:
        infoLabels['date'] = ''
      #subtitle = infoLabels['date']
      soup = self._strip_tags(item.description)  # , convertEntities=BSS.HTML_ENTITIES
      if 'subtitle' in item:
        infoLabels['plot'] = item.subtitle
      else:
        try:
          infoLabels['plot'] = soup.contents[0]
        except:
          infoLabels['plot'] = item.description.encode('utf-8', 'ignore')
      try:
        thumb = item.media_thumbnail[0]['url']
      except:
        try:
          thumb = item.thumbnail
        except:
          thumb = ''
      key = ''
      if 'itunes_duration' in item:
        infoLabels['duration'] = item.itunes_duration
      if 'enclosures' in item:
        for enclosure in item["enclosures"]:
          key = enclosure['href']
          try:
            infoLabels['size'] = int(enclosure['length'])
          except:
            infoLabels['size'] = 0
      if key == '':
        key = item.link
      if key.count('.torrent') > 0:
        hasInvalidItems = True
      if key.count('.html') > 0:
        hasInvalidItems = True
      if key.count('vimeo.com') > 0:
        if DEBUG:
          self.log('Geting vimeo video id to play with plugin.video.youtube add-on')
        video_id = key.split('clip_id=')[1]
        key = 'plugin://plugin.video.vimeo/?action=play_video&videoid=%s' % (video_id)
      if key.count('youtube.com') > 0:
        if DEBUG:
          self.log('Geting youtube video id to play with plugin.video.youtube add-on')
        video_id = key.split('=')[1].split('&')[0]
        thumb = 'http://i.ytimg.com/vi/%s/default.jpg' % video_id
        key = 'plugin://plugin.video.youtube/?action=play_video&videoid=%s' % (video_id)
      if thumb == '':
          thumb = __icon__
      if hasInvalidItems:
        if DEBUG:
          self.log('Invalid items. Unsupported media types found.\nURL: %s' % key)
        self._notification(__language__(30105), __language__(30106))
        return
      listitem = xbmcgui.ListItem(title, iconImage='DefaultVideo.png', thumbnailImage=thumb)
      listitem.setInfo(type='video', infoLabels=infoLabels)
      listitem.setProperty('IsPlayable', 'true')
      xbmcplugin.addDirectoryItems(int(sys.argv[1]), [(key, listitem, False)])
    # Sort methods and content type...
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    if infoLabels['date']:
      xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_TITLE)
    if infoLabels['duration']:
      xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    try:
      if infoLabels['size']:
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_SIZE)
    except:
      pass
    # End of directory...
    xbmcplugin.endOfDirectory(int(sys.argv[1]), True)

  def _subscribe(self):
    if DEBUG:
      self.log('_subscribe()')
    try:
      url = self.arguments('url', True)
      go_feed = False
    except:
      url = self._keyboard()
      go_feed = True
    if DEBUG:
      self.log('url of subscription: %s' % url)
    feed = feedparser.parse(urllib.urlopen(url))
    title = feed['feed']['title']
    try:
      thumb = feed['feed']['image']['href']
    except:
      thumb = ''
    try:
      desc = feed['feed']['summary']
    except:
      desc = ''
    if db.keys() != list():
      _id = len(db.keys()) + 1
    else:
      _id = 1
    if DEBUG:
      self.log('\nID: %s\nNAME: %s\nURL: %s\nTHUMB: %s' % \
               (_id, title, url, thumb))
    try:
      db[str(_id)] = {'name': title,
                      'url': url,
                      'thumbnail': thumb,
                      'description': desc}
      if DEBUG:
        self.log('succesfully subscribed.')
      self._notification(__language__(30101), __language__(30103))
    except:
      if DEBUG:
        self.log('ERROR while subscribe!')
    db.close()
    if go_feed:
      self.get_feed(url)
    else:
      return

  def _unsubscribe(self, _id):
    if DEBUG:
      self.log('_unubscribe()')
    try:
      del db[str(_id)]
      if DEBUG:
        self.log('succesfully unsubscribed.')
      self._notification(__language__(30102), __language__(30104))
    except:
      if DEBUG:
        self.log('ERROR while unsubscribe!')
    db.close()

  def _keyboard(self):
    if DEBUG:
      self.log('keyboard()')
    kb = xbmc.Keyboard()
    kb.setHeading('Add new RSS')
    kb.setDefault('http://')
    kb.doModal()
    if (kb.isConfirmed()):
      url = kb.getText()
      return url
    else:
      return

  def _strip_tags(self, _str):
    return re.sub(r'<[^<>]+>', '', _str)

  def _notification(self, title, message):
    if DEBUG:
      self.log('_notification()')
    xbmc.executebuiltin("Notification(%s, %s, %d, %s)" % \
                                     (title.encode('utf-8', 'ignore'), message.encode('utf-8', 'ignore'), 6000, __icon__))

  def arguments(self, arg, unquote=False):
    _arguments = dict(part.split('=') for part in sys.argv[2][1:].split('&'))
    if unquote:
      return urllib.unquote_plus(_arguments[arg])
    else:
      return _arguments[arg]

  def log(self, description):
    xbmc.log("[ADD-ON] '%s v%s': DEBUG: %s" % (__plugin__, __version__, description.encode('ascii', 'ignore')), xbmc.LOGNOTICE)


class DiskCacheFetcher:
  def __init__(self, cache_dir=None):
    # If no cache directory specified, use system temp directory
    if cache_dir is None:
      cache_dir = tempfile.gettempdir()
    if not os.path.exists(cache_dir):
      try:
        os.mkdir(cache_dir)
      except OSError, e:
        if e.errno == errno.EEXIST and os.path.isdir(cache_dir):
          # File exists, and it's a directory,
          # another process beat us to creating this dir, that's OK.
          pass
        else:
          # Our target dir is already a file, or different error,
          # relay the error!
          raise
    self.cache_dir = cache_dir

  def fetch(self, url, max_age=CACHE_TIME):
    # Use MD5 hash of the URL as the filename
    filename = hashlib.md5(url).hexdigest()
    filepath = os.path.join(self.cache_dir, filename)
    if os.path.exists(filepath):
      if int(time.time()) - os.path.getmtime(filepath) < max_age:
        if DEBUG:
          print 'File exists and reading from cache.'
        return open(filepath).read()
    # Retrieve over HTTP and cache, using rename to avoid collisions
    if DEBUG:
      print 'File not yet cached or cache time expired. File reading from URL and try to cache to disk'
    data = urllib2.urlopen(url).read()
    fd, temppath = tempfile.mkstemp()
    fp = os.fdopen(fd, 'w')
    fp.write(data)
    fp.close()
    shutil.move(temppath, filepath)
    return data

fetcher = DiskCacheFetcher(xbmc.translatePath(__cachedir__))

if __name__ == '__main__':
  Main()