import argparse,cProfile,pstats,io,signal
from runtime import *
a=argparse.ArgumentParser();a.add_argument('--case',default='025');a.add_argument('--q',type=int,default=1);a.add_argument('--engine',default='E0');a.add_argument('--limit',type=int,default=35);args=a.parse_args()
eng=load(None if args.engine=='E0' else ROOT/'fast_code');g=json.loads((OFF/f'data/case_{args.case}.json').read_bytes());p=json.loads((ROOT/f'results/initial/{args.case}.plan.json').read_bytes());cfg=settings(eng)
prof=cProfile.Profile();dest=ROOT/f'results/initial/{args.case}_q{args.q}_{args.engine}_bounded';row={}
def expired(*_):raise TimeoutError('research time cap')
signal.signal(signal.SIGALRM,expired);signal.alarm(args.limit)
try:
 t=time.perf_counter();prof.enable();r=evaluate(eng,args.q,g,p,cfg);prof.disable();signal.alarm(0);row.update(seconds=time.perf_counter()-t,makespan=r['makespan']);save_json(str(dest)+'.json.gz',r)
except Exception as ex:row.update(error=type(ex).__name__,message=str(ex),seconds=time.perf_counter()-t)
finally:
 prof.disable();signal.alarm(0);prof.dump_stats(str(dest)+'.pstats');stream=io.StringIO();pstats.Stats(prof,stream=stream).strip_dirs().sort_stats('cumtime').print_stats(40);Path(str(dest)+'.txt').write_text(stream.getvalue());save_json(str(dest)+'.run.json',row);print(row);print(stream.getvalue())
