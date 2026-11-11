import ast,os,sys
from pathlib import Path
from pyflakes.checker import Checker
from atelier.projects.scan import IGNORED

COMMON={'Path':'from pathlib import Path','PurePath':'from pathlib import PurePath','datetime':'from datetime import datetime',
        'date':'from datetime import date','timedelta':'from datetime import timedelta','dataclass':'from dataclasses import dataclass',
        'Counter':'from collections import Counter','defaultdict':'from collections import defaultdict','deque':'from collections import deque',
        'Optional':'from typing import Optional','Any':'from typing import Any','Callable':'from typing import Callable',
        'json':'import json','os':'import os','sys':'import sys','re':'import re','math':'import math','time':'import time',
        'subprocess':'import subprocess','shutil':'import shutil','threading':'import threading','asyncio':'import asyncio'}


def missing_imports(root,source):
    tree=ast.parse(source)
    missing={message.message_args[0] for message in Checker(tree).messages if message.__class__.__name__=='UndefinedName'}
    candidates={(name,COMMON[name]) for name in missing if name in COMMON}
    candidates.update((name,'import '+name) for name in missing if name in sys.stdlib_module_names)
    count=0
    for folder,dirs,files in os.walk(root):
        dirs[:]=[name for name in dirs if name not in IGNORED and not Path(folder,name).is_symlink()]
        for name in files:
            if not name.endswith('.py'):continue
            path=Path(folder,name);count+=1
            if count>3000:return sorted(candidates)
            try:
                if path.is_symlink() or path.stat().st_size>1_000_000:continue
                parts=list(path.relative_to(root).with_suffix('').parts)
                if parts[-1]=='__init__':parts.pop()
                if not parts or not all(part.isidentifier() for part in parts):continue
                module='.'.join(parts)
                if parts[-1] in missing:candidates.add((parts[-1],('from '+'.'.join(parts[:-1])+' import '+parts[-1]) if len(parts)>1 else 'import '+module))
                body=ast.parse(path.read_text(encoding='utf-8')).body
                for node in body:
                    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and node.name in missing:
                        candidates.add((node.name,f'from {module} import {node.name}'))
            except (OSError,UnicodeError,SyntaxError):continue
    return sorted(candidates)


def insert_import(source,statement):
    tree=ast.parse(source);lines=source.splitlines(True)
    position=tree.body[0].lineno-1 if tree.body else len(lines)
    for index,node in enumerate(tree.body):
        if index==0 and isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
            position=node.end_lineno;continue
        if isinstance(node,ast.ImportFrom) and node.module=='__future__':position=node.end_lineno;continue
        break
    lines.insert(position,statement+'\n')
    return ''.join(lines)


def code_changes(root,path,kind,name=None,start=0,end=0):
    from atelier.languages.rope_project import DirectoryProject
    from rope.refactor.extract import ExtractMethod,ExtractVariable
    from rope.refactor.importutils import ImportOrganizer
    project=DirectoryProject(str(root),ropefolder=None)
    try:
        resource=project.get_resource(Path(path).relative_to(root).as_posix())
        changes=ImportOrganizer(project).organize_imports(resource) if kind=='imports' else \
            (ExtractMethod if kind=='method' else ExtractVariable)(project,resource,start,end).get_changes(name)
        return project,changes
    except Exception:project.close();raise
