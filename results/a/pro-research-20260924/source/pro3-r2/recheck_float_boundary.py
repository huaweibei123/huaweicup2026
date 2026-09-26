"""Check S, without arithmetic rewrite, on the retained real binary64 boundary fixture."""
from runtime import *
if __name__=='__main__':
 folder=ROOT/'results/counterexamples/float_epochs_with_input';g=json.loads((folder/'graph.json').read_bytes());p=json.loads((folder/'plan.json').read_bytes())
 e,f=load(),load(ROOT/'fast_code');a=evaluate(e,2,g,p);b=evaluate(f,2,g,p);strict_equal(a,b)
 original=json.loads(gzip.decompress((folder/'E0.result.json.gz').read_bytes()));strict_equal(original,json.loads(json.dumps(a)))
 save_json(folder/'S.result.json.gz',b);save_json(folder/'S_check.json',{'new_E0_and_S_full_equal':True,'new_E0_matches_retained_fixture':True,'makespan':a['makespan'],'source':'retained all-DDR-input four-core n2048 fixture','not_a_timing_benchmark':True});print(a['makespan'],'new E0/S full equal')
