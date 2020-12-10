import logging
import sys
import json

from airflow.models import DagBag, DagRun
from airflow.utils import timezone
from airflow.exceptions import AirflowBadRequest
from airflow.operators.subdag_operator import SubDagOperator


def get_task_type(ti):
    if 'SubDagOperator' == ti.operator:
        task_type = 'subdag'
    else:
        task_type = 'task'
    return task_type


def _get_date(ti_date):
    if ti_date:
        ret_date = ti_date.isoformat()
    else:
        ret_date = ''

    return ret_date


def list_tasks(dag_name, exec_date):

    # dag_id = dag_name
    # execution_date = context['execution_date']
    # sdag = DagBag().get_dag(dag_id)
    if not (dag_name and exec_date):
        raise AirflowBadRequest("DAG name and execution date shouldn't be empty")

    res_map = {"dagId": dag_name, "executionDate": exec_date}
    task_list = []
    task_detail = dict()
    # execution date example : 2020-09-10T01:01:01+00:00
    ex_date = timezone.parse(exec_date)

    dag_id = dag_name
    dag_runs = DagRun.find(dag_id=dag_id, execution_date=ex_date)

    for dag_run in dag_runs:
        # logging.info("dag_run state: %s " % dag_run.state)
        execution_date = dag_run.execution_date
        res_map['dagState'] = dag_run.state
        res_map['taskSdate'] = ''
        res_map['taskEdate'] = ''
        res_map['taskExecDate'] = ''
        if dag_run.start_date:
            res_map['taskSdate'] = dag_run.start_date.isoformat()
        if dag_run.end_date:
            res_map['taskEdate'] = dag_run.end_date.isoformat()
        if execution_date:
            res_map['taskExecDate'] = execution_date.isoformat()
        # logging.info("dag_run execution_date : %s " % dag_run.execution_date)
        tasks = dag_run.get_task_instances()
        # logging.info("dag_run tasks : %s" % tasks)
        for task in tasks:
            # logging.info("per task info : %s" % str(task))
            task_detail.clear()
            # task_detail['dagId'] = task.dag_id
            if 'SubDagOperator' == task.operator:
                task_id = '{0}.{1}'.format(dag_id, task.task_id)
                task_detail = list_tasks(task_id, exec_date)
            else:
                # task_detail['taskSdate'] = task.start_date.isoformat()
                task_detail['taskSdate'] = _get_date(task.start_date)
                task_detail['taskEdate'] = _get_date(task.end_date)

            task_detail['dagId'] = task.dag_id
            task_detail['taskName'] = task.task_id
            task_detail['taskState'] = task.state
            task_detail['taskType'] = get_task_type(task)
            task_detail['taskExecDate'] = _get_date(execution_date)
            task_list.append(task_detail.copy())

    res_map['taskList'] = task_list

    return res_map







if __name__ == '__main__':
    res = list_tasks(dag_name=sys.argv[1], exec_date=sys.argv[2])
    logging.info("res is : %s" % json.dumps(res))
