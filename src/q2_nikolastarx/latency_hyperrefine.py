"""Experimental isolated-transfer-weighted placement, followed by fixed-owner retiming.

The connectivity sum is a heuristic proxy, not official Makespan or a bound.
"""
from __future__ import annotations

from .gap_hyperrefine import refine
from .gap_retime import retime
from .hypergraph_cost import HypergraphCost


def build(graph, plan, config, *, region_width=16):
    bandwidth = config['bandwidth']
    delay = config['cross_core_copy_delay_cycles']

    def model_factory(input_graph, eligible):
        return HypergraphCost(input_graph, eligible, proxy_bandwidth=bandwidth,
                              cross_core_delay=delay)

    placed, cut_detail = refine(
        graph, plan, config, region_width, model_factory=model_factory,
        cost_label='isolated_transfer_proxy_cycles')
    if placed is plan:
        return plan, {'placement': cut_detail, 'retime': None,
                      'scope': 'Static isolated-transfer proxy only; official quality unknown'}
    output, timing = retime(graph, placed, config)
    return output, {'placement': cut_detail, 'retime': timing,
                    'scope': 'Static isolated-transfer proxy and fixed-owner retiming; official quality unknown'}
