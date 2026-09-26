"""Acceptance transitions and source integrity; no network or evaluator calls."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from src.paper_acceptance.core import Board, Conflict, MARKER, ROOT
from src.paper_acceptance.app import CheckpointDocuments, Documents, TeamImages
from src.paper_acceptance.language import scan_text, import_author_report


class ReviewContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pdf = self.root / 'paper.pdf'; self.pdf.write_bytes(b'fixed source')
        self.cat = {'paper_sha256': hashlib.sha256(self.pdf.read_bytes()).hexdigest(),
                    'paper_commit': 'a'*40, 'standard_version': '1', 'repo': 'huaweibei123/huaweicup2026',
                    'issue': 217, 'members': ['author', 'reviewer', 'leader'], 'leader': 'leader',
                    'items': [{'id': 'L01', 'initial_state': 'needs_work', 'checks': ['full words', 'sources', 'scope']}],
                    'documents': [{'id': 'current', 'path': str(self.pdf), 'pages': 1,
                                   'sha256': hashlib.sha256(self.pdf.read_bytes()).hexdigest()}]}
        self.path = self.root / 'catalogue.json'; self.path.write_text(json.dumps(self.cat))
        self.board = Board(self.root / 'state', self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_team_figure_manifest_and_blob_integrity(self):
        gallery = TeamImages(self.board)
        self.assertGreaterEqual(len(gallery.by_id), 56)
        self.assertTrue(gallery.by_id['fang-fig42-a']['curation_priority'])
        for item_id, digest in (
            ('fang-fig5-1-a', '16e0b22aeb7849fdc986d8bb06548ac1c0a7378173fbaa2f93ae4ecb90b734f4'),
            ('fang-fig6-1-a', '9f134160b9c88c150229a4c3893583960bd2af4e74ea53dd3564d8b5dfaf8b90'),
        ):
            figure = gallery.by_id[item_id]
            self.assertTrue(figure['curation_priority'])
            self.assertEqual(figure['sha256'], digest)
            self.assertEqual(figure['fang_selection_state'], 'user_confirmed_a')
            self.assertNotIn('manuscript_placement', figure)
        self.assertLess(gallery.by_id['fang-fig5-1-a']['curation_rank'],
                        gallery.by_id['fang-fig42-a']['curation_rank'])
        original = gallery.by_id['fang-fig43-original-v2']
        preview = gallery.by_id['fang-fig43-insert-preview-v2']
        self.assertEqual(original['sha256'], 'c0ac9d63820aa9925fed7bda69769d7fa9248db8708b91391be81df82963db84')
        self.assertEqual(preview['sha256'], 'cc698a9e292c0c569417e91ed4e33e9b2129805f1197fec9ed1950c226c82779')
        self.assertEqual(original['family'], preview['family'])
        self.assertEqual(original['number'], preview['number'])
        self.assertEqual(original['number'], '图 D.2-1')
        self.assertEqual(original['fang_selection_state'], 'user_confirmed_original')
        self.assertEqual(original['review_stage'], 'review_pending')
        self.assertEqual(original['manuscript_placement']['checkpoint'], 'v8')
        self.assertEqual(original['manuscript_placement']['page'], 71)
        self.assertNotIn('manuscript_placement', preview)
        for original_id, preview_id, original_sha, preview_sha in (
            ('fang-fig54-layout-v1-original', 'fang-fig54-layout-v1-insert-preview',
             '9506e1f95cea2fa431ae98b1ae2b898bf3b7a916c4a5d3996154b73722ed1d57',
             'babc097056fa18ef6c1783120db832ca507203befe596b3084cf870976d45d6d'),
            ('fang-fig65-layout-v1-original', 'fang-fig65-layout-v1-insert-preview',
             '9e384b0029ddaca7658686730a853c144b128c6b02c99b3987b90a3b7e5a41ed',
             '7fb7c06d33f150ca2c4874ad2e584aca3819bedf1780d4feda2b0ffe8379bcde'),
        ):
            selected, paper_width = gallery.by_id[original_id], gallery.by_id[preview_id]
            self.assertEqual((selected['sha256'], paper_width['sha256']), (original_sha, preview_sha))
            self.assertEqual(selected['source_commit'], '5999965e8effe7baf60b7bda7b734ce86fdc0ba1')
            self.assertEqual(selected['family'], paper_width['family'])
            self.assertEqual(selected['fang_selection_state'], 'user_confirmed_workbench_original')
            self.assertNotIn('manuscript_placement', selected)
        self.assertEqual(gallery.by_id['fang-fig65-layout-v1-original']['number'], '图 6.9-1')
        self.assertFalse(gallery.by_id['fang-fig41']['curation_priority'])
        self.assertEqual(gallery.by_id['fang-fig41']['fang_selection_state'], 'not_adopted_current_algorithm')
        self.assertFalse(gallery.by_id['acceptance-case026-xy']['curation_priority'])
        self.assertFalse(gallery.by_id['acceptance-p1-834-flow-clean']['curation_priority'])
        self.assertEqual(gallery.by_id['fang-fig42-a']['curation_rank'], 3)
        self.assertGreaterEqual(len({item['family'] for item in gallery.by_id.values()}), 32)
        for item_id in (
            'acceptance-p2-cut-v4', 'acceptance-dataset-v4', 'acceptance-bound-gap-v4',
            'acceptance-p1-timeline-full-v4', 'acceptance-p1-timeline-zoom-v4',
            'acceptance-p2-timeline-full-v4', 'acceptance-p2-timeline-zoom-v4',
        ):
            self.assertIn(item_id, gallery.by_id)
            self.assertFalse(gallery.by_id[item_id]['curation_priority'])
            self.assertNotIn('manuscript_placement', gallery.by_id[item_id])
        checkpoints = json.loads((ROOT / 'docs/paper-acceptance/checkpoint-status.json').read_text())['checkpoints']
        v5 = {item['gallery_id']: item for item in next(c for c in checkpoints if c['id'] == 'v5')['figures_checked']}
        for item_id in ('farmer-fig52-v2', 'acceptance-p2-local-cut', 'acceptance-p2-three-plans', 'acceptance-p3-forest-decision'):
            placed = gallery.by_id[item_id]['manuscript_placement']
            self.assertEqual((placed['page'], placed['label']), (v5[item_id]['page'], v5[item_id]['label']))
            self.assertFalse(gallery.by_id[item_id]['curation_priority'])
        self.assertFalse(gallery.by_id['acceptance-p2-three-plans']['curation_priority'])
        self.assertFalse(gallery.by_id['acceptance-p2-local-cut']['curation_priority'])
        self.assertFalse(gallery.by_id['acceptance-p3-forest-decision']['curation_priority'])
        self.assertEqual(gallery.by_id['fang-fig41']['number'], '图 4.1-1')
        self.assertTrue(all(item['number'].startswith('图 ') for item in gallery.by_id.values()))
        raw = b'\x89PNG\r\n\x1a\nexample'
        item = {'size_bytes': len(raw), 'git_blob_sha1': hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
        self.assertEqual(TeamImages.checked(raw, item), raw)
        with self.assertRaisesRegex(ValueError, '哈希'):
            TeamImages.checked(raw[:-1]+b'X', item)

    def test_team_figure_registry_refreshes_without_server_restart(self):
        gallery = TeamImages(self.board)
        updated = copy.deepcopy(gallery.manifest)
        added = copy.deepcopy(updated['items'][0])
        added['id'] = 'fang-future-delivery'
        updated['items'].append(added)
        manifest_path = self.root / 'updated-figures.json'
        manifest_path.write_text(json.dumps(updated))
        gallery.manifest_path = manifest_path
        gallery.refresh()
        self.assertIn('fang-future-delivery', gallery.by_id)
        self.assertIn('fang-future-delivery', gallery.locks)

    def test_checkpoint_registry_keeps_new_freeze_separate_from_review_baseline(self):
        registry = json.loads((ROOT / 'docs/paper-acceptance/checkpoint-status.json').read_text())
        by_id = {item['id']: item for item in registry['checkpoints']}
        self.assertEqual(registry['latest_known_checkpoint'], 'v8')
        self.assertEqual(registry['acceptance_baseline'], 'CP01')
        self.assertEqual(by_id['v8']['kind'], 'frozen_published_checkpoint')
        self.assertEqual(by_id['v8']['pages'], 103)
        self.assertEqual(by_id['v8']['supplement_pages'], 57)
        self.assertEqual(len(by_id['v8']['figure_inventory']), 23)
        self.assertEqual(next(x for x in by_id['v8']['figures_checked'] if x['gallery_id'] == 'fang-fig43-original-v2')['page'], 71)
        self.assertFalse(by_id['v8']['human_final_acceptance'])
        self.assertIn(by_id['v8']['git_commit'], by_id['v8']['public_pdf_url'])
        self.assertEqual(by_id['v7']['kind'], 'frozen_published_checkpoint')
        self.assertIn(by_id['v7']['git_commit'], by_id['v7']['public_pdf_url'])
        self.assertEqual(by_id['v7']['pages'], 95)
        self.assertEqual({x['gallery_id'] for x in by_id['v7']['figures_checked']},
                         {x['gallery_id'] for x in by_id['v6']['figures_checked']})
        self.assertEqual(by_id['v6']['kind'], 'frozen_published_checkpoint')
        self.assertIn(by_id['v6']['git_commit'], by_id['v6']['public_pdf_url'])
        self.assertEqual(by_id['v6']['pages'], 95)
        self.assertEqual({x['gallery_id'] for x in by_id['v6']['figures_checked']},
                         {x['gallery_id'] for x in by_id['v5']['figures_checked']})
        self.assertEqual(by_id['v5']['kind'], 'frozen_published_checkpoint')
        self.assertIn(by_id['v5']['git_commit'], by_id['v5']['public_pdf_url'])
        self.assertEqual(by_id[registry['acceptance_baseline']]['pdf_sha256'],
                         json.loads((ROOT / 'docs/paper-acceptance/catalogue.json').read_text())['paper_sha256'])
        self.assertNotEqual(by_id[registry['latest_known_checkpoint']]['pdf_sha256'],
                            by_id[registry['acceptance_baseline']]['pdf_sha256'])
        self.assertIn(by_id['CP06']['git_commit'], by_id['CP06']['public_pdf_url'])
        self.assertEqual(len({by_id[x]['pdf_sha256'] for x in ('CP04', 'CP05', 'CP06')}), 3)

    def test_new_user_requests_keep_figure_and_typesetting_separate(self):
        handoffs = json.loads((ROOT / 'docs/paper-acceptance/handoffs.json').read_text())
        by_id = {item['annotation_id']: item for item in handoffs if item.get('annotation_id')}
        whitespace = by_id['USER-V8-P47-WHITESPACE-01']
        figure = by_id['USER-FANG-FIG53-OPTIMIZE-01']
        contents = by_id['USER-V9-AUTO-TOC-01']
        self.assertEqual(whitespace['url'], '/checkpoints/v8/47.png')
        self.assertIn('与Fang图5-3无关', whitespace['review'])
        self.assertIn('LYX旧版', figure['expected'])
        self.assertEqual(figure['state'], 'fang_source_received_rework_candidate_published')
        self.assertIn('5848146593', figure['notice_url'])
        self.assertIn('5848204054', figure['fang_receipt_url'])
        self.assertEqual(contents['state'], 'v9_layout_preflight_passed_not_frozen')
        self.assertEqual(whitespace['state'], 'v9_layout_preflight_passed_not_frozen')
        self.assertEqual(contents['preflight_sha256'], whitespace['preflight_sha256'])
        self.assertIn('正式最新版本仍为v8', contents['review'])
        self.assertEqual(len({x['source_request_sha256'] for x in (whitespace, figure, contents)}), 1)
        requests = json.loads((ROOT / 'docs/paper-acceptance/figure-requests.json').read_text())['requests']
        current = next(x for x in requests if x['id'] == 'FIG-FANG-5-3')
        self.assertEqual(current['user_annotation_id'], figure['annotation_id'])
        self.assertIn('待论文监督会话选版', current['state'])
        self.assertIn('5848146593', current['dispatch_url'])
        self.assertEqual(current['candidate_commit'], figure['candidate_commit'])
        gallery = TeamImages(self.board)
        revised = gallery.by_id['acceptance-fig53-rework-v1']
        self.assertEqual(revised['source_commit'], current['candidate_commit'])
        self.assertEqual(revised['review_stage'], 'review_pending')
        self.assertNotIn('manuscript_placement', revised)

    def test_v7_figure_review_keeps_user_words_separate_from_ai_advice(self):
        review = json.loads((ROOT / 'docs/paper-acceptance/figure-review-v7.json').read_text())
        checkpoints = json.loads((ROOT / 'docs/paper-acceptance/checkpoint-status.json').read_text())
        self.assertEqual(review['pdf_sha256'], next(x for x in checkpoints['checkpoints'] if x['id'] == 'v7')['pdf_sha256'])
        self.assertEqual(len(review['figure_coverage']), 20)
        self.assertEqual(review['figure_count'], 20)
        self.assertTrue(review['asset_hashes_matched'])
        self.assertEqual(review['user_annotation']['id'], 'USER-V7-FIGTEXT-01')
        self.assertIsNone(review['user_annotation']['rect'])
        self.assertIn('LaTeX', review['user_annotation']['user_verbatim'])
        self.assertNotEqual(review['user_annotation']['user_verbatim'],
                            review['user_annotation']['interpretation'])
        self.assertEqual(review['source_records']['publication_state'], 'local_unpublished')
        self.assertFalse(review['human_final_acceptance'])
        crop = review['user_annotation']['crop_candidate']
        self.assertEqual(crop['status'], 'board_preview_only_not_in_manuscript')
        self.assertEqual(crop['crop_box_pt_bottom_left'], [0, 23.639, 426.009, 478.639])
        for suffix in ('pdf', 'png'):
            path = ROOT / 'docs/paper-acceptance/candidates' / f'p28-figure-5.1-1-crop-candidate.{suffix}'
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), crop[f'preview_{suffix}_sha256'])

    def test_registered_checkpoint_refuses_changed_pdf(self):
        checkpoints = CheckpointDocuments(self.board)
        checkpoints.locations_file.write_text(json.dumps({'v5': str(self.pdf)}))
        fixed = {'pdf_sha256': hashlib.sha256(self.pdf.read_bytes()).hexdigest(), 'pages': 1,
                 'pdf_path': str(self.pdf)}
        with patch.object(CheckpointDocuments, 'record', return_value=fixed):
            self.assertEqual(checkpoints.locate('v5')[0], self.pdf.resolve())
            self.pdf.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError, '哈希'):
                checkpoints.locate('v5')

    def test_published_checkpoint_uses_fixed_git_object_when_local_file_is_missing(self):
        checkpoints = CheckpointDocuments(self.board)
        fixed = {'pdf_sha256': hashlib.sha256(self.pdf.read_bytes()).hexdigest(), 'pages': 1,
                 'pdf_path': 'paper.pdf', 'git_commit': 'a'*40}
        with patch.object(CheckpointDocuments, 'record', return_value=fixed), \
             patch('src.paper_acceptance.app.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=self.pdf.read_bytes())):
            pdf, _ = checkpoints.locate('v5')
            self.assertEqual(pdf.read_bytes(), self.pdf.read_bytes())
            self.assertEqual(pdf.parent, checkpoints.cache)

    def values(self, decision='comment', revision=0, actor='author'):
        return dict(item_id='L01', paper_sha256=self.cat['paper_sha256'], standard_hash=self.board.standard_hash,
                    expected_revision=revision, decision=decision, note='Checked the fixed paper and linked source.',
                    evidence=['https://github.com/huaweibei123/huaweicup2026/blob/'+'a'*40+'/paper/fixed.pdf'],
                    checks=[True]*3, session=actor+'/s-unit')

    def event(self, decision='comment', revision=0, actor='author'):
        return self.board.draft(self.values(decision, revision, actor), actor)

    def comment(self, event, cid, actor='author'):
        body=MARKER+'\n```json\n'+json.dumps(event)+'\n```'
        return dict(id=cid, body=body, user={'login': actor}, created_at='2026-09-26T01:00:00Z',
                    updated_at='2026-09-26T01:00:00Z', html_url=f'https://github.com/example/issuecomment-{cid}')

    def test_draft_does_not_approve(self):
        self.event('ready')
        state=self.board.snapshot()['items'][0]
        self.assertEqual((state['state'],state['revision']),('needs_work',0))

    def test_full_distinct_account_transition(self):
        a=self.comment(self.event('ready'),1)
        self.board.ingest_comments([a])
        b=self.comment(self.event('verified',1,'reviewer'),2,'reviewer')
        self.board.ingest_comments([a,b])
        c=self.comment(self.event('accepted',2,'leader'),3,'leader')
        self.assertTrue(self.board.ingest_comments([a,b,c])['all_accepted'])

    def test_same_account_new_session_is_not_independent(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        v=self.values('verified',1); v['session']='author/s-different'
        with self.assertRaisesRegex(ValueError,'独立复核'): self.board.draft(v,'author')

    def test_cannot_skip_independent_review(self):
        with self.assertRaises(ValueError): self.event('accepted',0,'leader')

    def test_concurrent_stale_review_is_retained_as_conflict(self):
        a,b=self.event(),self.event('needs_work')
        result=self.board.ingest_comments([self.comment(a,1),self.comment(b,2)])
        self.assertEqual(result['items'][0]['revision'],1)
        self.assertEqual(result['reviews'][1]['disposition'],'conflict')

    def test_new_paper_invalidates_old_acceptance(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        self.cat['paper_sha256']='b'*64; self.path.write_text(json.dumps(self.cat))
        new=Board(self.board.state,self.path).snapshot()
        self.assertEqual(new['items'][0]['revision'],0)
        self.assertEqual(new['reviews'][0]['disposition'],'conflict')

    def test_new_standard_invalidates_old_review(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        self.cat['standard_version']='2'; self.path.write_text(json.dumps(self.cat))
        self.assertEqual(Board(self.board.state,self.path).snapshot()['items'][0]['revision'],0)

    def test_missing_checks_and_moving_branch_are_rejected(self):
        v=self.values('ready'); v['checks'][0]=False
        with self.assertRaises(ValueError): self.board.draft(v,'author')
        v=self.values('ready'); v['evidence']=['https://github.com/huaweibei123/huaweicup2026/blob/main/paper.pdf']
        with self.assertRaises(ValueError): self.board.draft(v,'author')

    def test_comment_author_cannot_forge_session_identity(self):
        e=self.event(); self.board.ingest_comments([self.comment(e,1,'outsider')])
        self.assertEqual(self.board.snapshot()['items'][0]['revision'],0)

    def test_edited_source_invalidates_and_fresh_client_does_not_apply(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        a['body']+=' changed'; a['updated_at']='2026-09-26T02:00:00Z'
        self.assertEqual(self.board.ingest_comments([a])['items'][0]['revision'],0)
        fresh=Board(self.root/'fresh',self.path)
        self.assertEqual(fresh.ingest_comments([a])['items'][0]['revision'],0)

    def test_deleted_source_invalidates_dependent_review(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        b=self.comment(self.event('verified',1,'reviewer'),2,'reviewer'); self.board.ingest_comments([a,b])
        s=self.board.ingest_comments([b])
        self.assertEqual(s['items'][0]['state'],'needs_work')
        self.assertTrue(all(r['disposition']=='conflict' for r in s['reviews']))

    def test_repeated_sync_is_idempotent(self):
        c=self.comment(self.event(),1)
        self.board.ingest_comments([c]); self.board.ingest_comments([c])
        self.assertEqual(self.board.snapshot()['items'][0]['revision'],1)

    def test_uncertain_delivery_is_not_blindly_reposted(self):
        e=self.event()
        with self.board.db() as db: db.execute("UPDATE events SET disposition='uncertain'")
        with patch.object(self.board,'authenticate',return_value='author'), patch.object(self.board,'sync'):
            with self.assertRaisesRegex(ValueError,'不自动重发'): self.board.publish(e['id'])

    def test_shared_record_reconciliation_prevents_duplicate_post(self):
        e=self.event(); c=self.comment(e,1)
        with patch.object(self.board,'authenticate',return_value='author'), patch.object(self.board,'sync',side_effect=lambda:self.board.ingest_comments([c])):
            self.assertEqual(self.board.publish(e['id'])['url'],c['html_url'])

    def test_pdf_change_is_rejected_before_cached_render(self):
        d=Documents(self.board); d.locate('current')
        self.pdf.write_bytes(b'changed source with another length')
        with self.assertRaisesRegex(ValueError,'字节已变化'): d.locate('current')

    def test_scanner_does_not_flag_cross_core_sync_or_generic_verification(self):
        rules=[dict(term='(?<!跨)(?<!同)核同(?!步)',kind='优先审改',issue='test',requirement='test'),
               dict(term='核对(?=联合|与最多|比较)',kind='优先审改',issue='test',requirement='test')]
        e=scan_text('跨核同步。同核同 Pipe。重新核对工作量。字节核对。逐格核同。核对联合比较。',rules,'a'*64)
        self.assertEqual([x['term'] for x in e],['核同','核对'])
        for x in e: self.assertEqual(x['original'][x['match_start']:x['match_end']],x['term'])

    def test_author_self_report_does_not_change_acceptance(self):
        report={'schema_version':1,'paper_sha256':self.cat['paper_sha256'],
                'entries':[dict(chapter='a',line=1,original='old',issue='unclear',replacement='new',source='standard',status='accepted')]}
        with patch('src.paper_acceptance.language.subprocess.run') as run:
            run.return_value.stdout=json.dumps(report).encode()
            receipt=import_author_report(self.board,'c'*40,'paper/review.json')
        self.assertFalse(receipt['acceptance_changed'])
        self.assertEqual(self.board.snapshot()['items'][0]['state'],'needs_work')

    def test_import_refuses_wrong_baseline(self):
        with patch('src.paper_acceptance.language.subprocess.run') as run:
            run.return_value.stdout=json.dumps({'schema_version':1,'paper_sha256':'f'*64,'entries':[]}).encode()
            with self.assertRaisesRegex(ValueError,'哈希不同'): import_author_report(self.board,'c'*40,'paper/review.json')

class SemanticReportTests(unittest.TestCase):
    def test_annotation_identity_and_class_origin_are_required(self):
        from src.paper_acceptance.semantic import validate_workflow
        e={'annotation_id':'a1','event_key':'b'*64+':a1','source_commit':'a'*40,'paper_sha256':'b'*64,
           'original':'原文','user_comment_verbatim':'用户批注','page':1,'rect':[1,2,3,4]}
        c={'id':'c1','annotation_ids':['a1'],'title':'类别','mechanism':'缺陷','scope':['正文'],
           'positive_example':'实例','negative_example':'非实例','rules':['L07'],'coverage_status':'未完成'}
        data={'schema_version':2,'events':[e],'issue_classes':[c]}
        self.assertFalse(validate_workflow(data)['acceptance_changed'])
        data['events'].append(dict(e))
        with self.assertRaisesRegex(ValueError,'重复'):validate_workflow(data)
        data['events'].pop();c['annotation_ids']=['unknown']
        with self.assertRaisesRegex(ValueError,'回指'):validate_workflow(data)

    def packet(self):
        return {'source_commit':'a'*40,'standard_version':'2026-09-26.4',
                'entries':[{'id':'u1','path':'paper/ch.md','line':3,'line_end':3,'original':'待审原句。'}]}

    def report(self):
        return {'source_commit':'a'*40,'standard_version':'2026-09-26.4','worker':'sol-a',
                'coverage':[{'unit_id':'u1','assessment':'findings'}],
                'findings':[{'id':'f1','unit_id':'u1','path':'paper/ch.md','line':3,'original':'待审原句。','rules':['L13']}]}

    def test_old_version_cannot_be_attached_to_new_text(self):
        from src.paper_acceptance.semantic import combine_reports
        r=self.report();r['source_commit']='b'*40
        with self.assertRaisesRegex(ValueError,'新旧稿'):combine_reports([self.packet()],[r])

    def test_invented_quote_and_missing_coverage_are_rejected(self):
        from src.paper_acceptance.semantic import combine_reports
        r=self.report();r['findings'][0]['original']='不存在的原句'
        with self.assertRaisesRegex(ValueError,'连续原文'):combine_reports([self.packet()],[r])
        r=self.report();r['coverage']=[]
        with self.assertRaisesRegex(ValueError,'覆盖清单'):combine_reports([self.packet()],[r])

    def test_worker_acceptance_claim_is_not_imported(self):
        from src.paper_acceptance.semantic import combine_reports
        r=self.report();r['coverage'][0]['assessment']='accepted'
        with self.assertRaisesRegex(ValueError,'最终通过'):combine_reports([self.packet()],[r])
        result=combine_reports([self.packet()],[self.report()])
        self.assertEqual(result['findings'][0]['supervisor_status'],'pending')
        self.assertEqual(result['findings'][0]['author_status'],'not_delivered')

if __name__=='__main__': unittest.main()
