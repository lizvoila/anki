#-*- coding:utf-8 -*-

# import the main window object (mw) from aqt
# We're going to add a menu item below. First we want to create a function to
# be called when the menu item is activated.
import os
import re
import sys
import urllib2
import xml.etree.ElementTree
from StringIO import StringIO
import json
import aqt
from aqt import mw
from aqt.qt import *
from anki.hooks import addHook, runHook, wrap
from anki.importing import TextImporter
from aqt.addcards import AddCards
from aqt.modelchooser import ModelChooser
from aqt.studydeck import StudyDeck
from aqt.toolbar import Toolbar
from aqt.utils import shortcut, showInfo
# import trackback
from mdict.mdict_query import IndexBuilder
# from Queue import Queue


enable_youdao = 0

default_server = 'http://127.0.0.1:8000'
index_builder = None
dictpath = ''
savepath = os.path.join(sys.path[0], 'config')
serveraddr = default_server
use_local, use_server = False, False

rules = list()
with open(os.path.join(sys.path[0],'rules.json'),'rb') as f:
    rules = json.load(f)["fields"]

def find_rule(**kwargs):
    for rule in rules:
        # print rule.items(), kwargs.items()
        for arg in kwargs.items():
            if arg in rule.items():
                return rule

def _my_center_links(self):
    '''
    todo: use wrap
    '''
    links = [
            ["decks", _("Decks"), _("Shortcut key: %s") % "D"],
            ["add", _("Add"), _("Shortcut key: %s") % "A"],
            ["browse", _("Browse"), _("Shortcut key: %s") % "B"],
            ["query", _("Query"), _("Shortcut key: %s") % "Q"],
    ]
    self.link_handlers["query"] = _show_query_window  # self._queryLinkHandler
    # showInfo("custorm links")
    return self._linkHTML(links)
Toolbar._centerLinks = _my_center_links


def select_dict():
    global dictpath
    dictpath = QFileDialog.getOpenFileName(
        caption="select dictionary", directory=os.path.dirname(dictpath), filter="mdx Files(*.mdx)")
    if dictpath:
        dictpath = unicode(dictpath)
        mw.myEditLocalPath.setText(dictpath)


def okbtn_pressed():
    mw.myWidget.close()
    set_parameters()
    if use_local:
        index_mdx()


def set_parameters():
    global dictpath, serveraddr, use_local, use_server
    dictpath = unicode(mw.myEditLocalPath.text())
    serveraddr = unicode(mw.myEditServerAddr.text())
    use_local = mw.myCheckLocal.isChecked()
    use_server = mw.myCheckServer.isChecked()
    with open(savepath, 'wb') as f:
        p = '%d|%s|%d|%s' % (use_local, dictpath, use_server, serveraddr)
        f.write(p.encode('utf-8'))


def read_parameters():
    # try:
    with open(savepath, 'rb') as f:
        uls, path, uss, addr = f.read().strip().split('|')
        # showInfo(','.join([path, addr]))
        return bool(int(uls)), path.decode('utf-8'), bool(int(uss)), addr.decode('utf-8')
    # except:
    #     # showInfo("not exist")
    #     return False, "", False, default_server


class MdxIndexer(QThread):

    def __init__(self):
        QThread.__init__(self)

    def run(self):
        global index_builder
        index_builder = IndexBuilder(dictpath)


def index_mdx():
    mw.progress.start(immediate=True, label="Index building...")
    index_thread = MdxIndexer()
    index_thread.start()
    while not index_thread.isFinished():
        mw.app.processEvents()
        index_thread.wait(100)
    mw.progress.finish()


# AnkiQt.setupAddons = wrap(AnkiQt.setupAddons, index_mdx, "after")


def onCheckLocalStageChanged():
    global use_local
    use_local = mw.myCheckLocal.isChecked()
    if use_local:
        select_dict()


def onCheckServerStageChanged():
    global use_server
    use_server = mw.myCheckServer.isChecked()


def set_options():
    mw.myWidget = widget = QWidget()
    layout = QGridLayout()

    # showInfo('%d,%s,%d,%s' % (use_local, dictpath, use_server, serveraddr))
    mw.myCheckLocal = check_local = QCheckBox("Use Local Dict")
    check_local.setChecked(use_local)
    check_local.stateChanged.connect(onCheckLocalStageChanged)
    mw.myEditLocalPath = path_edit = QLineEdit()
    path_edit.setText(dictpath)

    mw.myCheckServer = check_server = QCheckBox("Use MDX Server")
    check_server.setChecked(use_server)
    check_local.stateChanged.connect(onCheckServerStageChanged)
    mw.myEditServerAddr = server_edit = QLineEdit()
    server_edit.setText(serveraddr)
    # online_check = QCheckBox("Enable Simple")
    ok_button = QPushButton("OK")
    ok_button.clicked.connect(okbtn_pressed)
    # layout.addWidget(QLabel("Set dictionary path: "))
    layout.addWidget(check_local, 0, 0)
    layout.addWidget(path_edit, 0, 1)
    layout.addWidget(check_server, 1, 0)
    layout.addWidget(server_edit, 1, 1)
    layout.addWidget(ok_button, 2, 0)
    widget.setLayout(layout)
    widget.show()


#######################################################

# "Query" Link in main window


def _query_link():
    word = mw.myWordEdit.text().strip()
    if word:
        # showInfo("Query %s" % word)
        mw.myWebView.load(
            QUrl('http://dict.baidu.com/s?wd=%s&ptype=english' % word))


def _show_query_window():
    mw.myWidget = widget = QWidget()
    layout = QGridLayout()
    mw.myWordEdit = word_edit = QLineEdit()
    ok_button = QPushButton("OK")
    ok_button.clicked.connect(_query_link)
    mw.myWebView = result_view = QWebView()
    layout.addWidget(QLabel("Word to query: "))
    layout.addWidget(word_edit)
    layout.addWidget(ok_button)
    layout.addWidget(result_view)

    widget.setLayout(layout)
    widget.show()
#################################################################



def my_setupButtons(self):
    bb = self.form.buttonBox
    ar = QDialogButtonBox.ActionRole
    self.queryButton = bb.addButton(_("Query"), ar)
    self.queryButton.clicked.connect(self.query)
    self.queryButton.setShortcut(QKeySequence("Ctrl+Q"))
    self.queryButton.setToolTip(shortcut(_("Query (shortcut: ctrl+q)")))


def query(self):
    for field in self.editor.note.fields:
        field = ''
    self.query_youdao()
    self.query_mdict()
    self.editor.currentField = 0
    self.editor.loadNote()


def query_youdao(self):
    self.editor.saveAddModeVars()
    note = self.editor.note
    word = note.fields[0]      # choose the first field as the word
    result = urllib2.urlopen(
        "http://dict.youdao.com/fsearch?client=deskdict&keyfrom=chrome.extension&pos=-1&doctype=xml&xmlVersion=3.2&dogVersion=1.0&vendor=unknown&appVer=3.1.17.4208&le=eng&q=%s" % word, timeout=5).read()
    file = StringIO(result)
    doc = xml.etree.ElementTree.parse(file)
    # fetch symbols
    symbol, uk_symbol, us_symbol = doc.findtext(".//phonetic-symbol"), doc.findtext(
        ".//uk-phonetic-symbol"), doc.findtext(".//us-phonetic-symbol")
    # showInfo(','.join([symbol, uk_symbol, us_symbol]))
    try:
        note.fields[1] = 'UK [%s] US [%s]' % (uk_symbol, us_symbol)
        # fetch explanations
        note.fields[3] = '<br>'.join([node.text for node in doc.findall(
            ".//custom-translation/translation/content")])
    except:
        showInfo("Template Error, online!")


def query_mdict(self):
    self.editor.saveAddModeVars()
    note = self.editor.note
    word = note.fields[0]      # choose the first field as the word
    result = None
    if use_local:
        try:
            if not index_builder:
                index_mdx()
            result = index_builder.mdx_lookup(word)
            if result:
                update_field(result[0], note)
        except AssertionError as e:
            # no valid mdict file found.
            pass
    if use_server:
        try:
            req = urllib2.urlopen(
                serveraddr + r'/' + word)
            result2 = req.read()
            if result2:
                update_field(result2, note)
        except:
            # server error
            pass


def convert_media_path(html):
    """
    convert the media path to actual path in anki's collection media folder.'
    """
    lst = list()
    mcss = re.findall('href="(\S+?\.css)"', html)
    lst.extend(list(set(mcss)))
    mjs = re.findall('src="([\w\./]\S+?\.js)"', html)
    lst.extend(list(set(mjs)))
    msrc = re.findall('<img.*?src="([\w\./]\S+?)".*?>', html)
    lst.extend(list(set(msrc)))
    # print lst
    newlist = ['_' + each.split('/')[-1] for each in lst]
    # print newlist
    for each in zip(lst, newlist):
        html = html.replace(each[0], each[1])
    return unicode(html)


def update_field(result_text, note):
    if len(note.fields) < 15:
        showInfo("Template Error, Mdx!")
        return
    result_text = convert_media_path(result_text)
    for rule in rules:
        feature = rule["feature"]
        if feature and feature in result_text:
            note.fields[rule["pos"]]=result_text


use_local, dictpath, use_server, serveraddr = read_parameters()
# showInfo(dictpath)
AddCards.query = query
AddCards.query_youdao = query_youdao
AddCards.query_mdict = query_mdict
AddCards.setupButtons = wrap(AddCards.setupButtons, my_setupButtons, "before")
# create a new menu item, "test"
action = QAction("Word Query", mw)
# set it to call testFunction when it's clicked
action.triggered.connect(set_options)
# and add it to the tools menu
mw.form.menuTools.addAction(action)


from collections import defaultdict

deck_name = u"test"
note_type_name = u"MultiDicts"

expsdict = defaultdict(str)


def query_youdao2(word):
    d = defaultdict(str)
    result = urllib2.urlopen(
        "http://dict.youdao.com/fsearch?client=deskdict&keyfrom=chrome.extension&pos=-1&doctype=xml&xmlVersion=3.2&dogVersion=1.0&vendor=unknown&appVer=3.1.17.4208&le=eng&q=%s" % word, timeout=5).read()
    doc = xml.etree.ElementTree.parse(StringIO(result))
    symbol, uk_symbol, us_symbol = unicode(doc.findtext(".//phonetic-symbol")), unicode(doc.findtext(
        ".//uk-phonetic-symbol")), unicode(doc.findtext(".//us-phonetic-symbol"))
    d[u'英美音标'] = unicode(u'UK [%s] US [%s]' % (uk_symbol, us_symbol))
    d[u'简要中文释义'] = unicode('<br>'.join([node.text for node in doc.findall(
        ".//custom-translation/translation/content")]))
    return d


def query_mdict2(word):
    d = defaultdict(str)
    result = None
    if use_local:
        try:
            if not index_builder:
                index_mdx()
            result = index_builder.mdx_lookup(word)
            if result:
                d = update_field2(result[0])
        except AssertionError as e:
            # no valid mdict file found.
            pass
    if use_server:
        try:
            req = urllib2.urlopen(
                serveraddr + r'/' + word)
            result2 = req.read()
            if result2:
                d.update(update_field2(result2))
        except:
            # server error
            pass
    return d


def update_field2(result_text):
    d = defaultdict(str)
    result_text = convert_media_path(result_text)
    for rule in rules:
        feature = rule["feature"]
        if feature and feature in result_text:
            d[rule["name"]] =result_text
    return d


def select():
    # select deck. Reuse deck if already exists, else add a desk with
    # deck_name.
    widget = QWidget()
    # prompt dialog to choose deck
    ret = StudyDeck(
        mw, current=None, accept=_("Choose"),
        title=_("Choose Deck"), help="addingnotes",
        cancel=False, parent=widget, geomKey="selectDeck")
    did = mw.col.decks.id(ret.name)
    mw.col.decks.select(did)
    if not ret.name:
        return None, None
    deck = mw.col.decks.byName(ret.name)

    def nameFunc():
        return sorted(mw.col.models.allNames())
    ret = StudyDeck(
        mw, names=nameFunc, accept=_("Choose"), title=_("Choose Note Type"),
        help="_notes", parent=widget,
        cancel=True, geomKey="selectModel")
    if not ret.name:
        return None, None
    model = mw.col.models.byName(ret.name)
    # deck['mid'] = model['id']
    # mw.col.decks.save(deck)
    return model, deck


def batch_import2():
    """
    Use addNote method to add the note one by one, but it can't check if the card exists now.
    """
    # index_mdx()
    filepath = QFileDialog.getOpenFileName(
        caption="select words table file", directory=os.path.dirname(dictpath), filter="All Files(*.*)")
    if not filepath:
        return
    model, deck = select()
    if not model:
        return
    if mw.col.conf.get("addToCur", True):
        did = mw.col.conf['curDeck']
        if mw.col.decks.isDyn(did):
            did = 1
    else:
        did = model['did']

    if did != model['did']:
        model['did'] = did
        mw.col.models.save(model)
    mw.col.decks.select(did)
    index_mdx()
    queue = list()
    # query
    query_thread = BatchQueryer(filepath, queue)
    query_thread.start()
    mw.progress.start(immediate=True, label="Batch Querying and Adding...")
    while not query_thread.isFinished():
        mw.app.processEvents()
        query_thread.wait(100)
    mw.progress.finish()

    with open('t.txt', 'wb') as fff:
        for data in queue:
            fff.write(','.join(data.values()) + '\n')
    # insert
    for data in queue:
        f = mw.col.newNote()
        for key in data:
            f[key] = data[key]
        mw.col.addNote(f)
    mw.reset()


class BatchQueryer(QThread):

    def __init__(self, filepath, queue):
        QThread.__init__(self)
        self.filepath = filepath
        self.queue = queue

    def run(self):
        with open(self.filepath, 'rb') as f:
            for i, line in enumerate(f):
                d = defaultdict(str)
                l = [each.strip() for each in line.split('\t')]
                word, sentence = l if len(l) == 2 else (l[0], "")
                if word:
                    m = re.search('\((.*?)\)', word)
                    if m:
                        word = m.groups()[0]
                    d[u'英语单词'] = unicode(word)
                    d[u'英语例句'] = unicode(sentence)
                    if enable_youdao == 1:
                        showInfo("enable youdao")
                        d.update(query_youdao2(word))
                    d.update(query_mdict2(word))
                    self.queue.append(d)


action = QAction("Batch Import...", mw)
# set it to call testFunction when it's clicked
action.triggered.connect(batch_import2)
# and add it to the tools menu
# mw.form.menuTools.addAction(action)
actionSep = QAction("", mw)
actionSep.setSeparator(True)
mw.form.menuCol.insertAction(mw.form.actionExit, actionSep)
mw.form.menuCol.insertAction(actionSep, action)
