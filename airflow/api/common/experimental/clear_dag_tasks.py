import logging
import sys
from airflow.models import DAG, DagBag
from airflow.exceptions import AirflowException
from airflow.utils import timezone
from airflow import models
from airflow import settings
from airflow.settings import STORE_SERIALIZED_DAGS


def get_dag(dag_id):
    dagbag = models.DagBag(settings.DAGS_FOLDER, store_serialized_dags=STORE_SERIALIZED_DAGS)
    # dagbag = DagBag("/usr/local/airflow/dags")
    if dag_id not in dagbag.dags:
        raise AirflowException(
            'dag_id could not be found: {}. Either the dag did not exist or it failed to '
            'parse.'.format(dag_id))
    dag = dagbag.dags[dag_id]
    return dag


def clear_dag_tasks(dag_id, task_id, start_date, end_date=None, downstream=False, upstream=False,
                    only_failed=False, only_running=False, include_subdags=True, include_parentdag=True):
    dag = get_dag(dag_id)

    dag_subset = dag.sub_dag(
        task_regex=task_id,
        include_downstream=downstream,
        include_upstream=upstream)
    logging.info("dag subsets : %s" % dag_subset)
    # NOTE: DAG.clear_dags needs a list of dag.
    dags = [dag_subset]

    count, all_tis = DAG.clear_dags(
        dags,
        start_date=timezone.parse(start_date),
        end_date=timezone.parse(end_date),
        only_failed=only_failed,
        only_running=only_running,
        confirm_prompt=False,
        include_subdags=include_subdags,
        include_parentdag=include_parentdag,
    )

    return count, all_tis


if __name__ == '__main__':
    counts, all_tasks = clear_dag_tasks(dag_id=sys.argv[1],
                                       task_id=sys.argv[2],
                                       start_date=sys.argv[3],
                                       end_date=sys.argv[4],
                                       downstream=True)

    logging.info("count : %s, all_tis: %s" % (counts, all_tasks))
