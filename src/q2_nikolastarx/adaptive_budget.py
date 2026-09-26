"""Unified frontier constructor with guarded active-core choice for waves."""
from . import active_core_wave, adaptive_frontier, adaptive_semantic, shared_input_wave
from .direct import UnsupportedStructure


def wave_route(index, cores, config):
    try:
        return active_core_wave.build_from_index(index, cores, config)
    except UnsupportedStructure as error:
        plan, detail = shared_input_wave.build_from_index(index, cores, config)
        return plan, {**detail, 'active_core_guard_rejected': str(error)}


def component_route(index, cores, config):
    return adaptive_frontier.component_route(index, cores, config,
                                             wave_builder=wave_route, allow_component_split=False)


def build(graph, cores, config):
    return adaptive_semantic.build(graph, cores, config, component_builder=component_route)


def main():
    adaptive_semantic.main(constructor=build, label='adaptive_budget')


if __name__ == '__main__':
    main()
