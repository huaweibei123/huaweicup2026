"""Split already rendered pages; retain global numbering and repair destinations."""
from pathlib import Path
import hashlib,json
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ArrayObject,DictionaryObject,NameObject,NumberObject,TextStringObject

P=Path(__file__).resolve().parents[2]
OUT=P/'checkpoints/v10'
PARTS=OUT/'parts'
PARTS.mkdir(exist_ok=True)
records=[]

def split(source,groups):
    reader=PdfReader(source)
    names=reader.named_destinations
    page_ids={page.indirect_reference.idnum:i for i,page in enumerate(reader.pages)}
    def resolve(dest):
        if isinstance(dest,str):
            obj=names.get(str(dest))
            if obj is None:return None
            return reader.get_destination_page_number(obj),list(obj.dest_array)[1:]
        if isinstance(dest,ArrayObject):
            page=dest[0]
            if hasattr(page,'idnum') and page.idnum in page_ids:
                return page_ids[page.idnum],list(dest)[1:]
        return None
    for start,end,name,title in groups:
        writer=PdfWriter()
        for page in reader.pages[start:end]:
            writer.add_page(page,excluded_keys=['/Annots'])
        def copy_outline(items,parent=None):
            latest=parent
            for item in items:
                if isinstance(item,list):
                    copy_outline(item,latest)
                else:
                    index=reader.get_destination_page_number(item)
                    latest=(writer.add_outline_item(item.title,index-start,parent=parent)
                            if start<=index<end else parent)
        copy_outline(reader.outline)
        local=remote=0
        for j in range(end-start):
            oldpage=reader.pages[start+j]
            newpage=writer.pages[j]
            originals=list(oldpage.get('/Annots',[]))
            newpage[NameObject('/Annots')]=ArrayObject()
            for oldref in originals:
                old=oldref.get_object()
                new=DictionaryObject({key:value.clone(writer) for key,value in old.items()
                                      if key not in ('/P','/A','/Dest')})
                new[NameObject('/P')]=newpage.indirect_reference
                newpage['/Annots'].append(writer._add_object(new))
                if '/A' in old:new[NameObject('/A')]=old['/A'].clone(writer)
                if old.get('/Subtype')!='/Link':continue
                action=old.get('/A',{})
                if hasattr(action,'get_object'):action=action.get_object()
                if '/Dest' in old:dest=old['/Dest']
                elif action.get('/S')=='/GoTo':dest=action.get('/D')
                else:continue
                target=resolve(dest)
                assert target is not None,(name,j,str(dest))
                index,tail=target
                new.pop('/Dest',None)
                if start<=index<end:
                    new[NameObject('/A')]=DictionaryObject({NameObject('/S'):NameObject('/GoTo'),NameObject('/D'):ArrayObject([writer.pages[index-start].indirect_reference,*tail])})
                    local+=1
                else:
                    other=next(g for g in groups if g[0]<=index<g[1])
                    new[NameObject('/A')]=DictionaryObject({NameObject('/S'):NameObject('/GoToR'),NameObject('/F'):TextStringObject(other[2]),NameObject('/D'):ArrayObject([NumberObject(index-other[0]),*tail])})
                    remote+=1
            writer.set_page_label(j,j,prefix=reader.page_labels[start+j])
        writer.add_metadata({'/Title':title,'/Subject':f'v10; original PDF pages {start+1}-{end}','/Author':''})
        target=PARTS/name
        writer.write(target)
        check=PdfReader(target)
        assert len(check.pages)==end-start
        for j,page in enumerate(check.pages):
            assert page.extract_text()==reader.pages[start+j].extract_text(),(name,j,'text changed')
            for ref in page.get('/Annots',[]):
                action=ref.get_object().get('/A',{})
                if hasattr(action,'get_object'):action=action.get_object()
                if action.get('/S')=='/GoToR':
                    group=next(g for g in groups if g[2]==action['/F'])
                    assert 0<=int(action['/D'][0])<group[1]-group[0]
        records.append(dict(file='parts/'+name,title=title,source=source.name,
                            original_pages=[start+1,end],pages=end-start,
                            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                            bytes=target.stat().st_size,local_links=local,cross_part_links=remote))

main=OUT/'anonymous-paper-v10.pdf'
r=PdfReader(main)
top=[x for x in r.outline if not isinstance(x,list)]
find=lambda prefix:next(r.get_destination_page_number(x) for x in top if x.title.startswith(prefix))
boundaries=[0,find('4 问题一'),find('5 问题二'),find('6 问题三'),find('7 实验'),find('附录 A'),len(r.pages)]
titles=['摘要目录与模型','问题一','问题二','问题三','实验结论与参考文献','附录说明与数学推导']
groups=[(a,min(b+1,len(r.pages)),f'v10-part-{i+1:02d}.pdf',f'论文 v10 · {title}') for i,(a,b,title) in enumerate(zip(boundaries,boundaries[1:],titles))]
split(main,groups)
supplement=OUT/'result-tables.pdf';count=len(PdfReader(supplement).pages)
groups=[(a,min(a+20,count),f'v10-results-{i+1:02d}.pdf',f'论文 v10 · 逐例结果附表 {i+1}') for i,a in enumerate(range(0,count,20))]
split(supplement,groups)
manifest=dict(version='v10',parts=records,
              split_by='Main chapter bookmarks, with shared transition page included in both adjacent booklets to retain preceding chapter endings; supplementary long tables in blocks of at most 20 pages',
              global_printed_page_numbers_preserved=True,
              page_text_readback_equal=True,
              link_destinations_checked=True,
              cross_part_viewer_support='GoToR destinations are valid relative files. Codex viewer interaction is not verified; open the named part directly if unsupported.')
(OUT/'parts-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([dict(file=x['file'],pages=x['pages'],original_pages=x['original_pages']) for x in records],ensure_ascii=False))
