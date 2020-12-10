import logging
import sys
import json
from airflow.models import DAG, DagBag
from airflow.exceptions import AirflowException
from airflow.utils import timezone
from airflow import models
from airflow import settings
from airflow.settings import STORE_SERIALIZED_DAGS


def task_tree(dag_id):
    dagbag = models.DagBag(settings.DAGS_FOLDER, store_serialized_dags=STORE_SERIALIZED_DAGS)
    # dagbag = DagBag("/usr/local/airflow/dags")
    if dag_id not in dagbag.dags:
        raise AirflowException(
            'dag_id could not be found: {}. Either the dag did not exist or it failed to '
            'parse.'.format(dag_id))
    dag = dagbag.get_dag(dag_id)
    if not dag:
        return None

    nodes = []
    edges = []
    for task in dag.tasks:
        nodes.append({
            'id': task.task_id
        })

    def get_downstream(task):
        for t in task.downstream_list:
            edge = {
                'source_id': task.task_id,
                'target_id': t.task_id,
            }
            if edge not in edges:
                edges.append(edge)
                get_downstream(t)

    for t in dag.roots:
        get_downstream(t)

    return nodes, edges


def task_tree_detail(dag_id):
    # dagbag = DagBag("/usr/local/airflow/dags")
    dagbag = models.DagBag(settings.DAGS_FOLDER, store_serialized_dags=STORE_SERIALIZED_DAGS)
    if dag_id not in dagbag.dags:
        raise AirflowException(
            'dag_id could not be found: {}. Either the dag did not exist or it failed to '
            'parse.'.format(dag_id))
    dag = dagbag.get_dag(dag_id)
    if not dag:
        return None

    nodes = []
    edges = []
    for task in dag.tasks:
        nodes.append({
            'id': task.task_id
        })

    def get_downstream(task):
        for t in task.downstream_list:
            edge = {
                'source_id': task.task_id,
                'target_id': t.task_id,
            }
            edge_tuple = (task.task_id, t.task_id)
            if edge not in edges:
                # edges.append(edge)
                edges.append(edge_tuple)
                get_downstream(t)

    for t in dag.roots:
        get_downstream(t)

    return nodes, edges


if __name__ == '__main__':
    nodes, edges = task_tree(dag_id=sys.argv[1])
    logging.info("nodes is : %s" % json.dumps(nodes))
    logging.info("edges is : %s" % json.dumps(edges))
