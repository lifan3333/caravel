"""Unit tests for Caravel"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from sqlalchemy.orm.session import make_transient

import json
import pickle
import unittest

from caravel import db, models

from .base_tests import CaravelTestCase


class ImportExportTests(CaravelTestCase):
    """Testing export import functionality for dashboards"""

    def __init__(self, *args, **kwargs):
        super(ImportExportTests, self).__init__(*args, **kwargs)

    @classmethod
    def delete_imports(cls):
        # Imported data clean up
        session = db.session
        for slc in session.query(models.Slice):
            if 'remote_id' in slc.params_dict:
                session.delete(slc)
        for dash in session.query(models.Dashboard):
            if 'remote_id' in dash.params_dict:
                session.delete(dash)
        for table in session.query(models.SqlaTable):
            if 'remote_id' in table.params_dict:
                session.delete(table)
        session.commit()

    @classmethod
    def setUpClass(cls):
        cls.delete_imports()

    @classmethod
    def tearDownClass(cls):
        cls.delete_imports()

    def create_slice(self, name, ds_id=None, id=None, db_name='main',
                     table_name='wb_health_population'):
        params = {
            'num_period_compare': '10',
            'remote_id': id,
            'datasource_name': table_name,
            'database_name': db_name,
            'schema': '',
        }

        if table_name and not ds_id:
            table = self.get_table_by_name(table_name)
            if table:
                ds_id = table.id

        return models.Slice(
            slice_name=name,
            datasource_type='table',
            viz_type='bubble',
            params=json.dumps(params),
            datasource_id=ds_id,
            id=id
        )

    def create_dashboard(self, title, id=0, slcs=[]):
        json_metadata = {'remote_id': id}
        return models.Dashboard(
            id=id,
            dashboard_title=title,
            slices=slcs,
            position_json='{"size_y": 2, "size_x": 2}',
            slug='{}_imported'.format(title.lower()),
            json_metadata=json.dumps(json_metadata)
        )

    def create_table(self, name, schema='', id=0, cols_names=[], metric_names=[]):
        params = {'remote_id': id, 'database_name': 'main'}
        table = models.SqlaTable(
            id=id,
            schema=schema,
            table_name=name,
            params=json.dumps(params)
        )
        for col_name in cols_names:
            table.columns.append(
                models.TableColumn(column_name=col_name))
        for metric_name in metric_names:
            table.metrics.append(models.SqlMetric(metric_name=metric_name))
        return table

    def get_slice(self, slc_id):
        return db.session.query(models.Slice).filter_by(id=slc_id).first()

    def get_dash(self, dash_id):
        return db.session.query(models.Dashboard).filter_by(
            id=dash_id).first()

    def get_dash_by_slug(self, dash_slug):
        return db.session.query(models.Dashboard).filter_by(
            slug=dash_slug).first()

    def get_table(self, table_id):
        return db.session.query(models.SqlaTable).filter_by(
            id=table_id).first()

    def get_table_by_name(self, name):
        return db.session.query(models.SqlaTable).filter_by(
            table_name=name).first()

    def assert_dash_equals(self, expected_dash, actual_dash):
        self.assertEquals(expected_dash.slug, actual_dash.slug)
        self.assertEquals(
            expected_dash.dashboard_title, actual_dash.dashboard_title)
        self.assertEquals(
            expected_dash.position_json, actual_dash.position_json)
        self.assertEquals(
            len(expected_dash.slices), len(actual_dash.slices))
        expected_slices = sorted(
            expected_dash.slices, key=lambda s: s.slice_name)
        actual_slices = sorted(
            actual_dash.slices, key=lambda s: s.slice_name)
        for e_slc, a_slc in zip(expected_slices, actual_slices):
            self.assert_slice_equals(e_slc, a_slc)

    def assert_table_equals(self, expected_ds, actual_ds):
        self.assertEquals(expected_ds.table_name, actual_ds.table_name)
        self.assertEquals(expected_ds.main_dttm_col, actual_ds.main_dttm_col)
        self.assertEquals(expected_ds.schema, actual_ds.schema)
        self.assertEquals(len(expected_ds.metrics), len(actual_ds.metrics))
        self.assertEquals(len(expected_ds.columns), len(actual_ds.columns))
        self.assertEquals(
            set([c.column_name for c in expected_ds.columns]),
            set([c.column_name for c in actual_ds.columns]))
        self.assertEquals(
            set([m.metric_name for m in expected_ds.metrics]),
            set([m.metric_name for m in actual_ds.metrics]))

    def assert_slice_equals(self, expected_slc, actual_slc):
        self.assertEquals(expected_slc.slice_name, actual_slc.slice_name)
        self.assertEquals(
            expected_slc.datasource_type, actual_slc.datasource_type)
        self.assertEquals(expected_slc.viz_type, actual_slc.viz_type)
        self.assertEquals(
            json.loads(expected_slc.params), json.loads(actual_slc.params))

    def test_export_1_dashboard(self):
        birth_dash = self.get_dash_by_slug('births')
        export_dash_url = (
            '/dashboardmodelview/export_dashboards_form?id={}&action=go'
            .format(birth_dash.id)
        )
        resp = self.client.get(export_dash_url)
        exported_dashboards = pickle.loads(resp.data)['dashboards']
        self.assert_dash_equals(birth_dash, exported_dashboards[0])
        self.assertEquals(
            birth_dash.id,
            json.loads(exported_dashboards[0].json_metadata)['remote_id'])

        exported_tables = pickle.loads(resp.data)['datasources']
        self.assertEquals(1, len(exported_tables))
        self.assert_table_equals(
            self.get_table_by_name('birth_names'), exported_tables[0])

    def test_export_2_dashboards(self):
        birth_dash = self.get_dash_by_slug('births')
        world_health_dash = self.get_dash_by_slug('world_health')
        export_dash_url = (
            '/dashboardmodelview/export_dashboards_form?id={}&id={}&action=go'
            .format(birth_dash.id, world_health_dash.id))
        resp = self.client.get(export_dash_url)
        exported_dashboards = sorted(pickle.loads(resp.data)['dashboards'],
                                     key=lambda d: d.dashboard_title)
        self.assertEquals(2, len(exported_dashboards))
        self.assert_dash_equals(birth_dash, exported_dashboards[0])
        self.assertEquals(
            birth_dash.id,
            json.loads(exported_dashboards[0].json_metadata)['remote_id']
        )

        self.assert_dash_equals(world_health_dash, exported_dashboards[1])
        self.assertEquals(
            world_health_dash.id,
            json.loads(exported_dashboards[1].json_metadata)['remote_id']
        )

        exported_tables = sorted(
            pickle.loads(resp.data)['datasources'], key=lambda t: t.table_name)
        self.assertEquals(2, len(exported_tables))
        self.assert_table_equals(
            self.get_table_by_name('birth_names'), exported_tables[0])
        self.assert_table_equals(
            self.get_table_by_name('wb_health_population'), exported_tables[1])

    def test_import_1_slice(self):
        expected_slice = self.create_slice('Import Me', id=10001);
        slc_id = models.Slice.import_obj(expected_slice, import_time=1989)
        slc = self.get_slice(slc_id)
        self.assertEquals(slc.datasource.perm, slc.perm)
        self.assert_slice_equals(expected_slice, slc)

        table_id = self.get_table_by_name('wb_health_population').id
        self.assertEquals(table_id, self.get_slice(slc_id).datasource_id)

    def test_import_2_slices_for_same_table(self):
        table_id = self.get_table_by_name('wb_health_population').id
        # table_id != 666, import func will have to find the table
        slc_1 = self.create_slice('Import Me 1', ds_id=666, id=10002)
        slc_id_1 = models.Slice.import_obj(slc_1)
        slc_2 = self.create_slice('Import Me 2', ds_id=666, id=10003)
        slc_id_2 = models.Slice.import_obj(slc_2)

        imported_slc_1 = self.get_slice(slc_id_1)
        imported_slc_2 = self.get_slice(slc_id_2)
        self.assertEquals(table_id, imported_slc_1.datasource_id)
        self.assert_slice_equals(slc_1, imported_slc_1)
        self.assertEquals(imported_slc_1.datasource.perm, imported_slc_1.perm)


        self.assertEquals(table_id, imported_slc_2.datasource_id)
        self.assert_slice_equals(slc_2, imported_slc_2)
        self.assertEquals(imported_slc_2.datasource.perm, imported_slc_2.perm)

    def test_import_slices_for_non_existent_table(self):
        with self.assertRaises(IndexError):
            models.Slice.import_obj(self.create_slice(
                'Import Me 3', id=10004, table_name='non_existent'))

    def test_import_slices_override(self):
        slc = self.create_slice('Import Me New', id=10005)
        slc_1_id = models.Slice.import_obj(slc, import_time=1990)
        slc.slice_name = 'Import Me New'
        slc_2_id = models.Slice.import_obj(
            self.create_slice('Import Me New', id=10005), import_time=1990)
        self.assertEquals(slc_1_id, slc_2_id)
        imported_slc = self.get_slice(slc_2_id)
        self.assert_slice_equals(slc, imported_slc)

    def test_import_empty_dashboard(self):
        empty_dash = self.create_dashboard('empty_dashboard', id=10001)
        imported_dash_id = models.Dashboard.import_obj(
            empty_dash, import_time=1989)
        imported_dash = self.get_dash(imported_dash_id)
        self.assert_dash_equals(empty_dash, imported_dash)

    def test_import_dashboard_1_slice(self):
        slc = self.create_slice('health_slc', id=10006)
        dash_with_1_slice = self.create_dashboard(
            'dash_with_1_slice', slcs=[slc], id=10002)
        imported_dash_id = models.Dashboard.import_obj(
            dash_with_1_slice, import_time=1990)
        imported_dash = self.get_dash(imported_dash_id)

        expected_dash = self.create_dashboard(
            'dash_with_1_slice', slcs=[slc], id=10002)
        make_transient(expected_dash)
        self.assert_dash_equals(expected_dash, imported_dash)
        self.assertEquals({"remote_id": 10002, "import_time": 1990},
                          json.loads(imported_dash.json_metadata))

    def test_import_dashboard_2_slices(self):
        e_slc = self.create_slice('e_slc', id=10007, table_name='energy_usage')
        b_slc = self.create_slice('b_slc', id=10008, table_name='birth_names')
        dash_with_2_slices = self.create_dashboard(
            'dash_with_2_slices', slcs=[e_slc, b_slc], id=10003)
        imported_dash_id = models.Dashboard.import_obj(
            dash_with_2_slices, import_time=1991)
        imported_dash = self.get_dash(imported_dash_id)

        expected_dash = self.create_dashboard(
            'dash_with_2_slices', slcs=[e_slc, b_slc], id=10003)
        make_transient(expected_dash)
        self.assert_dash_equals(imported_dash, expected_dash)
        self.assertEquals({"remote_id": 10003, "import_time": 1991},
                          json.loads(imported_dash.json_metadata))

    def test_import_override_dashboard_2_slices(self):
        e_slc = self.create_slice('e_slc', id=10009, table_name='energy_usage')
        b_slc = self.create_slice('b_slc', id=10010, table_name='birth_names')
        dash_to_import = self.create_dashboard(
            'override_dashboard', slcs=[e_slc, b_slc], id=10004)
        imported_dash_id_1 = models.Dashboard.import_obj(
            dash_to_import, import_time=1992)

        # create new instances of the slices
        e_slc = self.create_slice(
            'e_slc', id=10009, table_name='energy_usage')
        b_slc = self.create_slice(
            'b_slc', id=10010, table_name='birth_names')
        c_slc = self.create_slice('c_slc', id=10011, table_name='birth_names')
        dash_to_import_override = self.create_dashboard(
            'override_dashboard_new', slcs=[e_slc, b_slc, c_slc], id=10004)
        imported_dash_id_2 = models.Dashboard.import_obj(
            dash_to_import_override, import_time=1992)

        # override doesn't change the id
        self.assertEquals(imported_dash_id_1, imported_dash_id_2)
        expected_dash = self.create_dashboard(
            'override_dashboard_new', slcs=[e_slc, b_slc, c_slc], id=10004)
        make_transient(expected_dash)
        imported_dash = self.get_dash(imported_dash_id_2)
        self.assert_dash_equals(expected_dash, imported_dash)
        self.assertEquals({"remote_id": 10004, "import_time": 1992},
                          json.loads(imported_dash.json_metadata))

    def test_import_table_no_metadata(self):
        table = self.create_table('pure_table', id=10001)
        imported_t_id = models.SqlaTable.import_obj(table, import_time=1989)
        imported_table = self.get_table(imported_t_id)
        self.assert_table_equals(table, imported_table)

    def test_import_table_1_col_1_met(self):
        table = self.create_table(
            'table_1_col_1_met', id=10002,
            cols_names=["col1"], metric_names=["metric1"])
        imported_t_id = models.SqlaTable.import_obj(table, import_time=1990)
        imported_table = self.get_table(imported_t_id)
        self.assert_table_equals(table, imported_table)
        self.assertEquals(
            {'remote_id': 10002, 'import_time': 1990, 'database_name': 'main'},
            json.loads(imported_table.params))

    def test_import_table_2_col_2_met(self):
        table = self.create_table(
            'table_2_col_2_met', id=10003, cols_names=['c1', 'c2'],
            metric_names=['m1', 'm2'])
        imported_t_id = models.SqlaTable.import_obj(table, import_time=1991)

        imported_table = self.get_table(imported_t_id)
        self.assert_table_equals(table, imported_table)

    def test_import_table_override(self):
        table = self.create_table(
            'table_override', id=10003, cols_names=['col1'],
            metric_names=['m1'])
        imported_t_id = models.SqlaTable.import_obj(table, import_time=1991)

        table_over = self.create_table(
            'table_override', id=10003, cols_names=['new_col1', 'col2', 'col3'],
            metric_names=['new_metric1'])
        imported_table_over_id = models.SqlaTable.import_obj(
            table_over, import_time=1992)

        imported_table_over = self.get_table(imported_table_over_id)
        self.assertEquals(imported_t_id, imported_table_over.id)
        expected_table = self.create_table(
            'table_override', id=10003, metric_names=['new_metric1', 'm1'],
            cols_names=['col1', 'new_col1', 'col2', 'col3'])
        self.assert_table_equals(expected_table, imported_table_over)

    def test_import_table_override_idential(self):
        table = self.create_table(
            'copy_cat', id=10004, cols_names=['new_col1', 'col2', 'col3'],
            metric_names=['new_metric1'])
        imported_t_id = models.SqlaTable.import_obj(table, import_time=1993)

        copy_table = self.create_table(
            'copy_cat', id=10004, cols_names=['new_col1', 'col2', 'col3'],
            metric_names=['new_metric1'])
        imported_t_id_copy = models.SqlaTable.import_obj(
            copy_table, import_time=1994)

        self.assertEquals(imported_t_id, imported_t_id_copy)
        self.assert_table_equals(copy_table, self.get_table(imported_t_id))

if __name__ == '__main__':
    unittest.main()
