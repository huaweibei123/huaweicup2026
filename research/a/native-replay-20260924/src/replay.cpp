// Research kernel v0.1. NOT a replacement for the official plan/local compiler.
// Input: validated, immutable, precompiled task DAG + fixed FIFO per pipe.
// Integer wait/time domain only; caller checks conservative < 2^50 bound.
// Compile without fast-math/FMA contraction. Preserve EVERY DDR clock cut.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
#include <new>
#include <cfenv>

extern "C" {
struct Input {
    int32_t n, t, c;
    const int32_t *task_of, *pipe, *next_pipe, *heads, *pred_count;
    const int32_t *succ_off, *succ, *task_counts, *tp_off, *tp, *sort_rank;
    const int64_t *duration;
    const uint8_t *ddr;
    const int32_t *core_of, *order_off, *order;
    int64_t same_wait, cross_wait, max_iter;
    int32_t project_once;
};
struct Output {
    int64_t *op_start, *op_end, *task_start, *task_end, *stats;
    int64_t *audit;
    int64_t audit_cap;
};
// 0=ok, 1=deadlock, 2=no progress, 3=max_iter, 4=debug log exhausted,
// 5=allocation/other native failure, 6=rounding mode unsupported.
int replay(const Input *in, Output *out) noexcept {
  try {
    if (std::fegetround() != FE_TONEAREST) return 6;
    const auto &a = *in;
    const int slots = 4*a.c;
    std::vector<int32_t> pred(a.pred_count,a.pred_count+a.n);
    std::vector<int32_t> heads(a.heads,a.heads+4*a.t);
    std::vector<int32_t> left(a.task_counts,a.task_counts+a.t);
    std::vector<int32_t> active(a.c,-1), index(a.c,0), running(slots,-1);
    std::vector<int32_t> ddr_ids, ordered, positive, active_tasks;
    ddr_ids.reserve(slots); ordered.reserve(slots); positive.reserve(slots);
    active_tasks.reserve(a.c);
    std::vector<int64_t> run_end(slots,0), previous(a.c,-1);
    std::vector<double> remaining(a.n,0.0);
    std::vector<uint8_t> done(a.t,0);
    std::fill_n(out->op_start,a.n,-1); std::fill_n(out->op_end,a.n,-1);
    std::fill_n(out->task_start,a.t,-1); std::fill_n(out->task_end,a.t,-1);
    std::fill_n(out->stats,8,0);
    int64_t now=0, last=0, issue_count=0, project_count=0, adv_count=0, aw=0;
    int32_t tasks_left=a.t, max_active=0;
    auto advance = [&]() {
      ++adv_count;
      double elapsed = double(now-last);
      while (elapsed > 1e-9) {
        positive.clear();
        double minimum = std::numeric_limits<double>::infinity();
        for (int x: ddr_ids) if (remaining[x]>1e-9) {
          positive.push_back(x); minimum=std::min(minimum,remaining[x]);
        }
        if (positive.empty()) break;
        double finish_delta = minimum * double(positive.size());
        if (finish_delta >= elapsed-1e-9) {
          double share = elapsed / double(positive.size());
          for (int x: positive) remaining[x]=std::max(0.0,remaining[x]-share);
          break;
        }
        for (int x: positive) remaining[x]=std::max(0.0,remaining[x]-minimum);
        elapsed -= finish_delta;
      }
      last=now;
    };
    auto project = [&]() {
      if (ddr_ids.empty()) return;
      ++project_count;
      ordered.assign(ddr_ids.begin(),ddr_ids.end());
      std::sort(ordered.begin(),ordered.end(),[&](int x,int y) {
        double wx=std::max(0.0,remaining[x]), wy=std::max(0.0,remaining[y]);
        return wx<wy || (wx==wy && a.sort_rank[x]<a.sort_rank[y]);
      });
      double cursor=double(now), prev=0.0;
      int count=int(ordered.size());
      size_t i=0;
      while (i<ordered.size()) {
        double work=std::max(0.0,remaining[ordered[i]]);
        double difference=work-prev;
        double increment=difference*double(count);
        cursor += increment;
        size_t j=i;
        while (j<ordered.size() && std::abs(std::max(0.0,remaining[ordered[j]])-work)<=1e-9) {
          int op=ordered[j];
          int64_t end=static_cast<int64_t>(std::ceil(cursor-1e-9));
          out->op_end[op]=end;
          run_end[4*a.core_of[a.task_of[op]]+a.pipe[op]]=end;
          ++j;
        }
        count-=int(j-i); prev=work; i=j;
      }
    };
    auto release = [&](int task) -> int64_t {
      int core=a.core_of[task];
      for (int i=a.tp_off[task];i<a.tp_off[task+1];++i)
        if (!done[a.tp[i]]) return -1;
      int64_t r=previous[core]<0 ? 0 : previous[core]+a.same_wait;
      for (int i=a.tp_off[task];i<a.tp_off[task+1];++i) {
        int p=a.tp[i];
        if (a.core_of[p]!=core) r=std::max(r,out->task_end[p]+a.cross_wait);
      }
      return r;
    };
    for (int64_t iteration=0;iteration<a.max_iter;++iteration) {
      // Phase 1: ALL retirements, in original core x PIPES insertion order.
      advance();
      bool retired_ddr=false;
      for (int slot=0;slot<slots;++slot) {
        int op=running[slot];
        if (op<0 || run_end[slot]>now) continue;
        int task=a.task_of[op];
        --left[task];
        heads[4*task+a.pipe[op]]=a.next_pipe[op];
        if (a.ddr[op]) {
          auto pos=std::find(ddr_ids.begin(),ddr_ids.end(),op);
          if (pos!=ddr_ids.end()) ddr_ids.erase(pos);
          retired_ddr=true;
        }
        for (int j=a.succ_off[op];j<a.succ_off[op+1];++j) --pred[a.succ[j]];
        running[slot]=-1;
      }
      if (retired_ddr) project();
      active_tasks.clear();
      for (int x: active) if (x>=0) active_tasks.push_back(x);
      // Dense task indices ARE the official task insertion order.
      std::sort(active_tasks.begin(),active_tasks.end());
      for (int task: active_tasks) if (!left[task]) {
        int core=a.core_of[task]; done[task]=1; --tasks_left;
        out->task_end[task]=now; active[core]=-1; previous[core]=now; ++index[core];
      }
      // Phase 2: activate at most one task on each idle core.
      for (int core=0;core<a.c;++core) if (active[core]<0) {
        int j=a.order_off[core]+index[core];
        if (j>=a.order_off[core+1]) continue;
        int task=a.order[j]; int64_t r=release(task);
        if (r>=0 && r<=now) { active[core]=task; out->task_start[task]=now; }
      }
      // Phase 3: one eligible FIFO head, one slot, positive durations.
      // Issue does not advance FIFO or satisfy any dependency: no heap/fixpoint needed.
      bool new_ddr=false;
      for (int core=0;core<a.c;++core) {
        int task=active[core]; if (task<0) continue;
        for (int p=0;p<4;++p) {
          int slot=4*core+p, op=heads[4*task+p];
          if (running[slot]>=0 || op<0 || pred[op]!=0) continue;
          ++issue_count; out->op_start[op]=now; out->op_end[op]=now+a.duration[op];
          running[slot]=op; run_end[slot]=out->op_end[op];
          if (a.ddr[op]) {
            advance(); remaining[op]=double(a.duration[op]); ddr_ids.push_back(op);
            max_active=std::max(max_active,int32_t(ddr_ids.size())); new_ddr=true;
            if (!a.project_once || out->audit) project();
            if (out->audit) {
              int64_t needed=3+2*int64_t(ddr_ids.size());
              if (aw+needed>out->audit_cap) return 4;
              out->audit[aw++]=now; out->audit[aw++]=op;
              out->audit[aw++]=int64_t(ddr_ids.size());
              ordered.assign(ddr_ids.begin(),ddr_ids.end());
              std::sort(ordered.begin(),ordered.end(),[&](int x,int y){return a.sort_rank[x]<a.sort_rank[y];});
              for (int x: ordered) {out->audit[aw++]=x;out->audit[aw++]=out->op_end[x];}
            }
          }
        }
      }
      // No dependency/FIFO transition occurs on issue; only the final projection
      // is read by the next iteration. Debug mode retains every log snapshot.
      if (new_ddr && a.project_once && !out->audit) project();
      if (tasks_left==0) {
        out->stats[0]=now; out->stats[1]=iteration+1; out->stats[2]=issue_count;
        out->stats[3]=project_count; out->stats[4]=adv_count; out->stats[5]=aw;
        out->stats[6]=max_active; return 0;
      }
      int64_t nxt=std::numeric_limits<int64_t>::max();
      for (int slot=0;slot<slots;++slot) if (running[slot]>=0) nxt=std::min(nxt,run_end[slot]);
      for (int core=0;core<a.c;++core) if (active[core]<0) {
        int j=a.order_off[core]+index[core];
        if (j<a.order_off[core+1]) {int64_t r=release(a.order[j]);if(r>now)nxt=std::min(nxt,r);}
      }
      if (nxt==std::numeric_limits<int64_t>::max()) return 1;
      if (nxt<=now) return 2;
      now=nxt;
    }
    return 3;
  } catch (...) { return 5; }
}
}
