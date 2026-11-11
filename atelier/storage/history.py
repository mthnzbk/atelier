import difflib,gzip,hashlib,json,time
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPlainTextEdit, QPushButton


class FileHistory:
    def __init__(self,root):self.root=Path(root)/'history'
    def folder(self,path):return self.root/hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()
    def entries(self,path):
        try:return json.loads((self.folder(path)/'index.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):return []
    def snapshot(self,path,text):
        digest=hashlib.sha256(text.encode('utf-8')).hexdigest();entries=self.entries(path)
        if entries and entries[0]['sha']==digest:return
        folder=self.folder(path);folder.mkdir(parents=True,exist_ok=True)
        filename=f'{time.time_ns()}-{digest[:12]}.txt.gz'
        with gzip.open(folder/filename,'wt',encoding='utf-8',compresslevel=1) as output:output.write(text)
        entries.insert(0,{'file':filename,'time':time.time(),'sha':digest,'size':len(text.encode('utf-8'))})
        for old in entries[40:]:
            target=(folder/old['file']).resolve()
            if target.parent==folder.resolve():target.unlink(missing_ok=True)
        temporary=folder/'index.tmp';temporary.write_text(json.dumps(entries[:40]),encoding='utf-8');temporary.replace(folder/'index.json')
    def read(self,path,entry):
        folder=self.folder(path).resolve();target=(folder/entry['file']).resolve()
        if target.parent!=folder:raise ValueError('Geçersiz geçmiş kaydı')
        with gzip.open(target,'rt',encoding='utf-8') as source:return source.read()


class HistoryDialog(QDialog):
    def __init__(self,window,doc):
        super().__init__(window);self.window,self.doc=window,doc
        self.setWindowTitle('Dosya geçmişi · '+doc.path.name);self.resize(950,650)
        layout=QVBoxLayout(self);self.listing=QListWidget();self.listing.setMaximumHeight(160);layout.addWidget(self.listing)
        self.preview=QPlainTextEdit(readOnly=True);layout.addWidget(self.preview,1)
        button=QPushButton('Seçili sürümü editöre geri yükle');layout.addWidget(button);button.clicked.connect(self.restore)
        self.versions=window.file_history.entries(doc.path)
        for entry in self.versions:
            self.listing.addItem(datetime.fromtimestamp(entry['time']).strftime('%Y-%m-%d %H:%M:%S')+f" · {entry['size']} bayt")
        self.listing.currentRowChanged.connect(self.show_version)
        if self.versions:self.listing.setCurrentRow(0)
        else:button.setEnabled(False);self.preview.setPlainText('İlk kayıttan sonra geçmiş oluşur.')
    def show_version(self,index):
        if index<0:return
        self.text=self.window.file_history.read(self.doc.path,self.versions[index])
        difference=''.join(difflib.unified_diff(self.doc.editor.toPlainText().splitlines(True),self.text.splitlines(True),fromfile='Mevcut',tofile='Seçili geçmiş'))
        self.preview.setPlainText(difference or 'Mevcut içerikle aynı.')
    def restore(self):
        if self.doc not in self.window.documents:return
        self.window.replace_document_text(self.doc,self.text)
        self.accept()
