# -*- coding: utf-8 -*-
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import airflow.api

from airflow.api.common.experimental import pool as pool_api
from airflow.api.common.experimental import trigger_dag as trigger
from airflow.api.common.experimental.get_dag_runs import get_dag_runs
from airflow.api.common.experimental.get_task import get_task
from airflow.api.common.experimental.get_task_instance import get_task_instance
from airflow.api.common.experimental.get_code import get_code
from airflow.api.common.experimental.get_dag_run_state import get_dag_run_state
from airflow.api.common.experimental.list_tasks import list_tasks
from airflow.api.common.experimental.graph_sort import topological_sort_edges, graph_sort
from airflow.api.common.experimental.clear_dag_tasks import clear_dag_tasks
from airflow.exceptions import AirflowException
from airflow.utils.log.logging_mixin import LoggingMixin
from airflow.utils.strings import to_boolean
from airflow.utils import timezone
from airflow.www_rbac.app import csrf
from airflow import models
from airflow.utils.db import create_session

from flask import g, Blueprint, jsonify, request, url_for

_log = LoggingMixin().log

requires_authentication = airflow.api.API_AUTH.api_auth.requires_authentication

api_experimental = Blueprint('api_experimental', __name__)


@csrf.exempt
@api_experimental.route('/dags/<string:dag_id>/dag_runs', methods=['POST'])
@requires_authentication
def trigger_dag(dag_id):
    """
    Trigger a new dag run for a Dag with an execution date of now unless
    specified in the data.
    """
    data = request.get_json(force=True)

    run_id = None
    if 'run_id' in data:
        run_id = data['run_id']

    conf = None
    if 'conf' in data:
        conf = data['conf']

    execution_date = None
    if 'execution_date' in data and data['execution_date'] is not None:
        execution_date = data['execution_date']

        # Convert string datetime into actual datetime
        try:
            execution_date = timezone.parse(execution_date)
        except ValueError:
            error_message = (
                'Given execution date, {}, could not be identified '
                'as a date. Example date format: 2015-11-16T14:34:15+00:00'
                .format(execution_date))
            _log.info(error_message)
            response = jsonify({'error': error_message})
            response.status_code = 400

            return response

    replace_microseconds = (execution_date is None)
    if 'replace_microseconds' in data:
        replace_microseconds = to_boolean(data['replace_microseconds'])

    try:
        # dr = trigger.trigger_dag(dag_id, run_id, conf, execution_date, replace_microseconds)
        dr = trigger.trigger_dag(dag_id, run_id, conf, execution_date, replace_microseconds=False)
    except AirflowException as err:
        _log.error(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response

    if getattr(g, 'user', None):
        _log.info("User {} created {}".format(g.user, dr))

    response = jsonify(
        message="Created {}".format(dr),
        execution_date=dr.execution_date.isoformat(),
        run_id=dr.run_id
    )
    return response


@api_experimental.route('/dags/<string:dag_id>/dag_runs', methods=['GET'])
@requires_authentication
def dag_runs(dag_id):
    """
    Returns a list of Dag Runs for a specific DAG ID.
    :query param state: a query string parameter '?state=queued|running|success...'
    :param dag_id: String identifier of a DAG
    :return: List of DAG runs of a DAG with requested state,
    or all runs if the state is not specified
    """
    try:
        state = request.args.get('state')
        dagruns = get_dag_runs(dag_id, state)
    except AirflowException as err:
        _log.info(err)
        response = jsonify(error="{}".format(err))
        response.status_code = 400
        return response

    return jsonify(dagruns)


@api_experimental.route('/test', methods=['GET'])
@requires_authentication
def test():
    return jsonify(status='OK')


@api_experimental.route('/dags/<string:dag_id>/code', methods=['GET'])
@requires_authentication
def get_dag_code(dag_id):
    """Return python code of a given dag_id."""
    try:
        return get_code(dag_id)
    except AirflowException as err:
        _log.info(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response


@api_experimental.route('/dags/<string:dag_id>/tasks/<string:task_id>', methods=['GET'])
@requires_authentication
def task_info(dag_id, task_id):
    """Returns a JSON with a task's public instance variables. """
    try:
        info = get_task(dag_id, task_id)
    except AirflowException as err:
        _log.info(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response

    # JSONify and return.
    fields = {k: str(v)
              for k, v in vars(info).items()
              if not k.startswith('_')}
    return jsonify(fields)


# ToDo: Shouldn't this be a PUT method?
@api_experimental.route('/dags/<string:dag_id>/paused/<string:paused>', methods=['GET'])
@requires_authentication
def dag_paused(dag_id, paused):
    """(Un)pauses a dag"""

    DagModel = models.DagModel
    with create_session() as session:
        orm_dag = (
            session.query(DagModel)
                   .filter(DagModel.dag_id == dag_id).first()
        )
        if paused == 'true':
            orm_dag.is_paused = True
        else:
            orm_dag.is_paused = False
        session.merge(orm_dag)
        session.commit()

    return jsonify({'response': 'ok'})


@api_experimental.route('/dags/<string:dag_id>/paused', methods=['GET'])
@requires_authentication
def dag_is_paused(dag_id):
    """Get paused state of a dag"""

    is_paused = models.DagModel.get_dagmodel(dag_id).is_paused

    return jsonify({'is_paused': is_paused})


@api_experimental.route(
    '/dags/<string:dag_id>/dag_runs/<string:execution_date>/tasks/<string:task_id>',
    methods=['GET'])
@requires_authentication
def task_instance_info(dag_id, execution_date, task_id):
    """
    Returns a JSON with a task instance's public instance variables.
    The format for the exec_date is expected to be
    "YYYY-mm-DDTHH:MM:SS", for example: "2016-11-16T11:34:15". This will
    of course need to have been encoded for URL in the request.
    """

    # Convert string datetime into actual datetime
    try:
        execution_date = timezone.parse(execution_date)
    except ValueError:
        error_message = (
            'Given execution date, {}, could not be identified '
            'as a date. Example date format: 2015-11-16T14:34:15+00:00'
            .format(execution_date))
        _log.info(error_message)
        response = jsonify({'error': error_message})
        response.status_code = 400

        return response

    try:
        info = get_task_instance(dag_id, task_id, execution_date)
    except AirflowException as err:
        _log.info(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response

    # JSONify and return.
    fields = {k: str(v)
              for k, v in vars(info).items()
              if not k.startswith('_')}
    return jsonify(fields)


@api_experimental.route(
    '/dags/<string:dag_id>/dag_runs/<string:execution_date>',
    methods=['GET'])
@requires_authentication
def dag_run_status(dag_id, execution_date):
    """
    Returns a JSON with a dag_run's public instance variables.
    The format for the exec_date is expected to be
    "YYYY-mm-DDTHH:MM:SS", for example: "2016-11-16T11:34:15". This will
    of course need to have been encoded for URL in the request.
    """

    # Convert string datetime into actual datetime
    try:
        execution_date = timezone.parse(execution_date)
    except ValueError:
        error_message = (
            'Given execution date, {}, could not be identified '
            'as a date. Example date format: 2015-11-16T14:34:15+00:00'.format(
                execution_date))
        _log.info(error_message)
        response = jsonify({'error': error_message})
        response.status_code = 400

        return response

    try:
        info = get_dag_run_state(dag_id, execution_date)
    except AirflowException as err:
        _log.info(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response

    return jsonify(info)


@api_experimental.route('/latest_runs', methods=['GET'])
@requires_authentication
def latest_dag_runs():
    """Returns the latest DagRun for each DAG formatted for the UI. """
    from airflow.models import DagRun
    dagruns = DagRun.get_latest_runs()
    payload = []
    for dagrun in dagruns:
        if dagrun.execution_date:
            payload.append({
                'dag_id': dagrun.dag_id,
                'execution_date': dagrun.execution_date.isoformat(),
                'start_date': ((dagrun.start_date or '') and
                               dagrun.start_date.isoformat()),
                'dag_run_url': url_for('Airflow.graph', dag_id=dagrun.dag_id,
                                       execution_date=dagrun.execution_date)
            })
    return jsonify(items=payload)  # old flask versions dont support jsonifying arrays


@api_experimental.route('/pools/<string:name>', methods=['GET'])
@requires_authentication
def get_pool(name):
    """Get pool by a given name."""
    try:
        pool = pool_api.get_pool(name=name)
    except AirflowException as err:
        _log.error(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response
    else:
        return jsonify(pool.to_json())


@api_experimental.route('/pools', methods=['GET'])
@requires_authentication
def get_pools():
    """Get all pools."""
    try:
        pools = pool_api.get_pools()
    except AirflowException as err:
        _log.error(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response
    else:
        return jsonify([p.to_json() for p in pools])


@csrf.exempt
@api_experimental.route('/pools', methods=['POST'])
@requires_authentication
def create_pool():
    """Create a pool."""
    params = request.get_json(force=True)
    try:
        pool = pool_api.create_pool(**params)
    except AirflowException as err:
        _log.error(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response
    else:
        return jsonify(pool.to_json())


@csrf.exempt
@api_experimental.route('/pools/<string:name>', methods=['DELETE'])
@requires_authentication
def delete_pool(name):
    """Delete pool."""
    try:
        pool = pool_api.delete_pool(name=name)
    except AirflowException as err:
        _log.error(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response
    else:
        return jsonify(pool.to_json())


@api_experimental.route('/taskslist/<string:dag_id>/dagruns/<string:exec_date>', methods=['GET'])
@requires_authentication
def task_list(dag_id, exec_date):
    """
    Returns a JSON with a dag_run's task instance list.
    The format for the exec_date is expected to be
    "YYYY-mm-DDTHH:MM:SS", for example: "2016-11-16T11:34:15+00:00". This will
    of course need to have been encoded for URL in the request.
    """
    _log.info("into task list api")
    try:
        tasks = list_tasks(dag_name=dag_id, exec_date=exec_date)
        task_edges = topological_sort_edges(dag_id)
        tasks['taskList'] = graph_sort(task_edges, tasks)
    except AirflowException as err:
        _log.error(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response
    else:
        return jsonify(tasks)


@csrf.exempt
@api_experimental.route('/clear/<string:dag_id>/tasks', methods=['POST'])
@requires_authentication
def clear_dag(dag_id):
    data = request.get_json(force=True)
    _log.info("clear_dag data : %s " % data)

    try:
        task_id = data['task_id']
        start_date = data['start_date']
        end_date = data['end_date']
        downstream = data['downstream']
    except ValueError as err:
        err_msg = "One or more given parameters not validation. \nUsage: " + \
                  "{'task_id':'', 'start_date':'', 'end_date':'', " + \
                  "'downstream':True}\n Example date format: 2015-11-16T14:34:15+00:00"
        _log.error(err)
        response = jsonify({'error': err_msg})
        response.status_code = 400

        return response

    # try:
    #     _log.info("task_id: %s, start_date: %s" % (task_id, start_date))
    #     start_date = timezone.parse(start_date)
    #     end_date = timezone.parse(end_date)
    # except ValueError:
    #     error_message = (
    #         'Given execution date, {}, could not be identified '
    #         'as a date. Example date format: 2015-11-16T14:34:15+00:00'
    #         .format(execution_date))
    #     _log.info(error_message)
    #     response = jsonify({'error': error_message})
    #     response.status_code = 400

    #     return response

    try:
        count, all_tis = clear_dag_tasks(dag_id, task_id, start_date, end_date, downstream)
    except AirflowException as err:
        _log.error(err)
        response = jsonify(error="{}".format(err))
        response.status_code = err.status_code
        return response

    if 0 == count:
        ret = {'count': 0, 'allTasks': []}
    else:
        ret = {'count': count, 'allTasks': [str(t) for t in all_tis]}

    return jsonify(ret)


