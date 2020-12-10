import networkx as nx
import logging
import json
from task_tree import task_tree_detail

TASK_TYPE_SUBDAG = 'subdag'
TASK_TYPE_TASK = 'task'


def topological_sort_edges(dag_id):
    task_nodes, task_edges = task_tree_detail(dag_id)
    di_graph = nx.DiGraph()
    di_graph.add_edges_from(task_edges)
    tp_sort_edges = list(nx.topological_sort(di_graph))
    return tp_sort_edges


def graph_sort(tp_sort_edges, dag_tasks_detail):
    task_list = dag_tasks_detail['taskList']
    sorted_task_list = []
    for edge in tp_sort_edges:
        for ti in task_list:
            if edge == ti['taskName']:
                if TASK_TYPE_SUBDAG == ti['taskType']:
                    # add 2020-11-17, fix dag id of subdag tasks.
                    subdag_id = '{0}.{1}'.format(ti['dagId'], ti['taskName'])
                    sdag_tp_sort_edges = topological_sort_edges(subdag_id)
                    # sdag_tp_sort_edges = topological_sort_edges(ti['dagId'])
                    ti['taskList'] = graph_sort(sdag_tp_sort_edges, ti)
                    sorted_task_list.append(ti.copy())
                else:
                    if 'skipped' != ti['taskState']:
                        sorted_task_list.append(ti.copy())

    return sorted_task_list


# dag_detail = list_tasks("vm_scaling", "2020-10-30T09:14:42+00:00")
# task_edges = topological_sort_edges("vm_scaling")
# dag_detail['taskList'] = graph_sort(task_edges, dag_detail)
#
# logging.info("dag_detail : %s" % json.dumps(dag_detail))

