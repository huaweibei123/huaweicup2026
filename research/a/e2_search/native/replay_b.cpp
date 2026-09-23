// Scene B: one prepared Task per core. Retire all -> release -> issue FIFO heads.
// Independent of the P1 binary. Preserve every event cut and binary64 operation.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
#include <cfenv>

extern "C" {
struct InputB {
  int32_t n, c;
  const int32_t *slot, *next_pipe, *heads, *pred_count, *succ_off, *succ;
  const int32_t *cross_count, *cross_off, *cross_succ, *sort_rank;
  const int64_t *duration;
  const uint8_t *ddr;
  int64_t cross_wait, max_iter;
};
struct OutputB { int64_t *op_start, *op_end, *stats; };

int replay_b(const InputB *in, OutputB *out) noexcept {
  try {
    if (std::fegetround()!=FE_TONEAREST) return 6;
    const auto &a=*in;
    const int slots=4*a.c;
    std::vector<int32_t> pred(a.pred_count,a.pred_count+a.n);
    std::vector<int32_t> cross(a.cross_count,a.cross_count+a.n);
    std::vector<int32_t> heads(a.heads,a.heads+slots), running(slots,-1);
    std::vector<int64_t> release(a.n,0), ends(slots,0);
    std::vector<double> remaining(a.n,0.0);
    std::vector<int32_t> active, ordered, positive;
    active.reserve(slots); ordered.reserve(slots); positive.reserve(slots);
    std::fill_n(out->op_start,a.n,-1); std::fill_n(out->op_end,a.n,-1);
    std::fill_n(out->stats,8,0);
    int64_t now=0,last=0,left=a.n,issues=0,projects=0,advances=0;
    auto advance=[&]() {
      ++advances;
      double elapsed=double(now-last);
      while(elapsed>1e-9) {
        positive.clear(); double minimum=std::numeric_limits<double>::infinity();
        for(int x:active) if(remaining[x]>1e-9) {
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
      last=now;
    };
    auto project=[&]() {
      if(active.empty()) return;
      ++projects; ordered.assign(active.begin(),active.end());
      std::sort(ordered.begin(),ordered.end(),[&](int x,int y) {
        double wx=std::max(0.0,remaining[x]),wy=std::max(0.0,remaining[y]);
        return wx<wy || (wx==wy && a.sort_rank[x]<a.sort_rank[y]);
      });
      double cursor=double(now),prev=0.0;
      int count=int(ordered.size()); size_t i=0;
      while(i<ordered.size()) {
        double work=std::max(0.0,remaining[ordered[i]]);
        cursor+=(work-prev)*double(count);
        size_t j=i;
        while(j<ordered.size() && std::abs(std::max(0.0,remaining[ordered[j]])-work)<=1e-9) {
          int op=ordered[j];
          out->op_end[op]=static_cast<int64_t>(std::ceil(cursor-1e-9));
          ends[a.slot[op]]=out->op_end[op]; ++j;
        }
        count-=int(j-i); prev=work; i=j;
      }
    };
    for(int64_t iteration=0;iteration<a.max_iter;++iteration) {
      advance(); bool retired=false;
      for(int s=0;s<slots;++s) {
        int op=running[s]; if(op<0 || ends[s]>now) continue;
        --left; heads[s]=a.next_pipe[op]; running[s]=-1;
        if(a.ddr[op]) {
          auto p=std::find(active.begin(),active.end(),op);
          if(p!=active.end()) active.erase(p);
          retired=true;
        }
        for(int j=a.succ_off[op];j<a.succ_off[op+1];++j) --pred[a.succ[j]];
        for(int j=a.cross_off[op];j<a.cross_off[op+1];++j) {
          int target=a.cross_succ[j]; --cross[target];
          release[target]=std::max(release[target],out->op_end[op]+a.cross_wait);
        }
      }
      if(retired) project();
      // One FIFO head per idle pipe; issuing neither advances FIFO nor completes
      // dependencies. Future ready-head releases are included in next-time cuts.
      for(int s=0;s<slots;++s) {
        int op=heads[s];
        if(running[s]>=0 || op<0 || pred[op] || cross[op] || release[op]>now) continue;
        ++issues; running[s]=op; out->op_start[op]=now;
        out->op_end[op]=now+a.duration[op]; ends[s]=out->op_end[op];
        if(a.ddr[op]) { advance(); remaining[op]=double(a.duration[op]); active.push_back(op); project(); }
      }
      if(!left) {
        out->stats[0]=now; out->stats[1]=iteration+1; out->stats[2]=issues;
        out->stats[3]=projects; out->stats[4]=advances; return 0;
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
