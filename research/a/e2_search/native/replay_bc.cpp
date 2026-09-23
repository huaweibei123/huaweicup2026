// P2/P3 shared global replay. P3 has independent DDR and CACHE_READ pools.
// Cache is read-only FIFO: insert at COPY_IN retirement, never refresh a hit.
// Deliberately separate ABI/library from frozen P2 replay_b and original P1.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
#include <deque>
#include <cfenv>

extern "C" {
struct InputBC {
  int32_t n, c, cache_mode, keys;
  const int32_t *slot, *next_pipe, *heads, *pred_count, *succ_off, *succ;
  const int32_t *cross_count, *cross_off, *cross_succ, *sort_rank, *cache_key;
  const int64_t *duration, *hit_duration, *transfer_bytes;
  const uint8_t *ddr;
  int64_t cross_wait, max_iter, cache_capacity;
};
struct OutputBC {
  int64_t *op_start, *op_end, *memory_path, *stats, *final_keys, *final_sizes, *events;
  int64_t event_cap;
};
int replay_bc_abi() noexcept { return 1; }

int replay_bc(const InputBC *in, OutputBC *out) noexcept {
  try {
    if(std::fegetround()!=FE_TONEAREST) return 6;
    const auto &a=*in; const int slots=4*a.c;
    std::vector<int32_t> pred(a.pred_count,a.pred_count+a.n), cross(a.cross_count,a.cross_count+a.n);
    std::vector<int32_t> heads(a.heads,a.heads+slots), running(slots,-1), op_pool(a.n,-1);
    std::vector<int64_t> release(a.n,0), ends(slots,0), cache_size(a.keys,0);
    std::vector<double> remaining(a.n,0.0);
    std::vector<int32_t> active[2],ordered,positive,evicted;
    std::vector<uint8_t> cached(a.keys,0);
    std::deque<int32_t> fifo;
    for(auto &pool:active) pool.reserve(slots);
    ordered.reserve(slots); positive.reserve(slots);
    std::fill_n(out->op_start,a.n,-1); std::fill_n(out->op_end,a.n,-1);
    std::fill_n(out->memory_path,a.n,0); std::fill_n(out->stats,16,0);
    int64_t now=0,last[2]={0,0},left=a.n,issues=0,projects=0,advances=0,used=0,logpos=0;
    auto event=[&](int kind,int op,int key,int64_t bytes,int64_t used_bytes,const std::vector<int32_t> &removed) {
      if(!out->events) return true;
      if(logpos+7+int64_t(removed.size())>out->event_cap) return false;
      out->events[logpos++]=kind; out->events[logpos++]=now;
      out->events[logpos++]=op; out->events[logpos++]=key; out->events[logpos++]=bytes;
      out->events[logpos++]=used_bytes; out->events[logpos++]=int64_t(removed.size());
      for(int k:removed) out->events[logpos++]=k;
      return true;
    };
    auto advance=[&](int pool) {
      ++advances; double elapsed=double(now-last[pool]);
      while(elapsed>1e-9) {
        positive.clear(); double minimum=std::numeric_limits<double>::infinity();
        for(int x:active[pool]) if(remaining[x]>1e-9) {
          positive.push_back(x); minimum=std::min(minimum,remaining[x]);
        }
        if(positive.empty()) break;
        double finish_delta=minimum*double(positive.size());
        if(finish_delta>=elapsed-1e-9) {
          double share=elapsed/double(positive.size());
          for(int x:positive) remaining[x]=std::max(0.0,remaining[x]-share);
          break;
        }
        for(int x:positive) remaining[x]=std::max(0.0,remaining[x]-minimum);
        elapsed-=finish_delta;
      }
      last[pool]=now;
    };
    auto project=[&](int pool) {
      if(active[pool].empty()) return;
      ++projects; ordered.assign(active[pool].begin(),active[pool].end());
      std::sort(ordered.begin(),ordered.end(),[&](int x,int y) {
        double wx=std::max(0.0,remaining[x]),wy=std::max(0.0,remaining[y]);
        return wx<wy || (wx==wy && a.sort_rank[x]<a.sort_rank[y]);
      });
      double cursor=double(now),prev=0.0; int count=int(ordered.size()); size_t i=0;
      while(i<ordered.size()) {
        double work=std::max(0.0,remaining[ordered[i]]);
        cursor+=(work-prev)*double(count); size_t j=i;
        while(j<ordered.size() && std::abs(std::max(0.0,remaining[ordered[j]])-work)<=1e-9) {
          int op=ordered[j]; out->op_end[op]=static_cast<int64_t>(std::ceil(cursor-1e-9));
          ends[a.slot[op]]=out->op_end[op]; ++j;
        }
        count-=int(j-i); prev=work; i=j;
      }
    };
    for(int64_t iteration=0;iteration<a.max_iter;++iteration) {
      advance(0); if(a.cache_mode) advance(1);
      bool retired[2]={false,false};
      for(int s=0;s<slots;++s) {
        int op=running[s]; if(op<0 || ends[s]>now) continue;
        --left; heads[s]=a.next_pipe[op]; running[s]=-1;
        int pool=op_pool[op];
        if(pool>=0) {
          auto p=std::find(active[pool].begin(),active[pool].end(),op);
          if(p!=active[pool].end()) active[pool].erase(p);
          retired[pool]=true;
        }
        // cache_key is assigned ONLY to COPY_IN; zero-size keys still insert.
        int key=a.cache_key[op]; int64_t bytes=a.transfer_bytes[op];
        if(a.cache_mode && key>=0 && bytes<=a.cache_capacity && !cached[key]) {
          evicted.clear();
          while(!fifo.empty() && used+bytes>a.cache_capacity) {
            int old=fifo.front(); fifo.pop_front(); used-=cache_size[old]; cached[old]=0; evicted.push_back(old);
          }
          cached[key]=1; cache_size[key]=bytes; fifo.push_back(key); used+=bytes;
          if(!event(2,op,key,bytes,used,evicted)) return 4;
        }
        for(int j=a.succ_off[op];j<a.succ_off[op+1];++j) --pred[a.succ[j]];
        for(int j=a.cross_off[op];j<a.cross_off[op+1];++j) {
          int target=a.cross_succ[j]; --cross[target];
          release[target]=std::max(release[target],out->op_end[op]+a.cross_wait);
        }
      }
      for(int p=0;p<2;++p) if(retired[p]) project(p);
      for(int s=0;s<slots;++s) {
        int op=heads[s];
        if(running[s]>=0 || op<0 || pred[op] || cross[op] || release[op]>now) continue;
        int key=a.cache_key[op]; int64_t bytes=a.transfer_bytes[op];
        bool eligible=a.cache_mode && key>=0 && bytes>0;
        bool hit=eligible && cached[key];
        int64_t duration=hit ? a.hit_duration[op] : a.duration[op];
        ++issues; running[s]=op; out->op_start[op]=now; out->op_end[op]=now+duration; ends[s]=out->op_end[op];
        if(eligible) {
          ++out->stats[hit ? 6 : 7]; out->stats[hit ? 8 : 9]+=bytes;
          out->memory_path[op]=hit ? 2 : 1;
          evicted.clear(); if(!event(hit ? 1 : 0,op,key,bytes,0,evicted)) return 4;
        }
        int pool=hit ? 1 : (a.ddr[op] ? 0 : -1);
        if(pool>=0) {
          op_pool[op]=pool; out->memory_path[op]=pool+1;
          advance(pool); remaining[op]=double(duration); active[pool].push_back(op); project(pool);
        }
      }
      if(!left) {
        out->stats[0]=now; out->stats[1]=iteration+1; out->stats[2]=issues;
        out->stats[3]=projects; out->stats[4]=advances; out->stats[5]=logpos;
        out->stats[10]=used; out->stats[11]=int64_t(fifo.size());
        int j=0; for(int key:fifo) { out->final_keys[j]=key; out->final_sizes[j]=cache_size[key]; ++j; }
        return 0;
      }
      int64_t next=std::numeric_limits<int64_t>::max();
      for(int s=0;s<slots;++s) {
        if(running[s]>=0) next=std::min(next,ends[s]);
        else {
          int op=heads[s];
          if(op>=0 && !pred[op] && !cross[op] && release[op]>now) next=std::min(next,release[op]);
        }
      }
      if(next==std::numeric_limits<int64_t>::max()) return 1;
      if(next<=now) return 2;
      now=next;
    }
    return 3;
  } catch(...) { return 5; }
}
}
