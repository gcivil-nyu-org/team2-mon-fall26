from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase


class ReviewUniquenessMigrationTests(TransactionTestCase):
    migrate_from = [('reviews', '0001_initial')]
    migrate_to = [('reviews', '0002_review_votes_and_uniqueness')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state(self.migrate_from).apps
        self.addCleanup(self.restore_schema)
        self.Review = self.old_apps.get_model('reviews', 'Review')
        User = self.old_apps.get_model('auth', 'User')
        Hotspot = self.old_apps.get_model('hotspots', 'Hotspot')
        self.author = User.objects.create(username='legacy-author')
        self.hotspot = Hotspot.objects.create(
            hotspot_id=99001,
            source_object_id=99001,
            name='Legacy hotspot',
            location_description='Migration test location',
            latitude='40.75',
            longitude='-73.98',
            borough='Manhattan',
            provider='Test provider',
            access_type='Free',
            source_acquired_on=date(2026, 10, 14),
        )

    def restore_schema(self):
        # These rows exist only in the disposable test database. The migration
        # itself never deletes reviews or chooses which legacy review to retain.
        self.old_apps.get_model('reviews', 'Review').objects.all().delete()
        MigrationExecutor(connection).migrate(self.migrate_to)

    def upgrade(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        return executor.loader.project_state(self.migrate_to).apps

    def snapshot(self):
        return list(self.Review.objects.order_by('pk').values())

    def test_unique_legacy_reviews_upgrade_without_changing_data(self):
        self.Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=4, body='Keep this review.'
        )
        demo_author = self.old_apps.get_model('auth', 'User').objects.create(
            username='legacy-demo', is_active=False
        )
        self.Review.objects.create(
            hotspot=self.hotspot, author=demo_author, rating=3, body='', is_demo=True
        )
        before = self.snapshot()

        apps = self.upgrade()

        self.assertEqual(self.snapshot(), before)
        self.assertIn('reviews_reviewvote', connection.introspection.table_names())
        self.assertEqual(apps.get_model('reviews', 'ReviewVote').objects.count(), 0)
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, 'reviews_review')
        self.assertTrue(constraints['one_review_per_author_per_hotspot']['unique'])

    def test_duplicate_legacy_reviews_fail_before_ddl_and_allow_a_clean_retry(self):
        self.Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=4, body='Original review.'
        )
        duplicate = self.Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=2, body='Legacy second review.'
        )
        before = self.snapshot()
        self.assertNotIn('reviews_reviewvote', connection.introspection.table_names())

        with self.assertRaisesMessage(RuntimeError, 'multiple reviews exist'):
            self.upgrade()

        self.assertEqual(self.snapshot(), before)
        self.assertNotIn('reviews_reviewvote', connection.introspection.table_names())
        self.assertNotIn(self.migrate_to[0], MigrationRecorder(connection).applied_migrations())

        # Explicitly correct the fixture to simulate an operator's data decision;
        # production data is never automatically deduplicated by the migration.
        duplicate.delete()
        corrected = self.snapshot()
        self.upgrade()
        self.assertEqual(self.snapshot(), corrected)
        self.assertIn(self.migrate_to[0], MigrationRecorder(connection).applied_migrations())
        self.assertIn('reviews_reviewvote', connection.introspection.table_names())
