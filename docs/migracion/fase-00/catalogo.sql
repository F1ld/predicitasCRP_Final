-- Solo lectura. Ejecutar sobre clones aislados; no expone filas ni passwords.
SELECT jsonb_pretty(jsonb_build_object(
  'server_version', current_setting('server_version'),
  'timezone', current_setting('TimeZone'),
  'database', current_database(),
  'alembic', (SELECT jsonb_agg(version_num ORDER BY version_num) FROM alembic_version),
  'tables', (SELECT jsonb_agg(jsonb_build_object('name', tablename, 'owner', tableowner, 'rls', rowsecurity) ORDER BY tablename) FROM pg_tables WHERE schemaname = 'public'),
  'columns', (SELECT jsonb_agg(jsonb_build_object('table', table_name, 'column', column_name, 'type', data_type, 'udt', udt_name, 'nullable', is_nullable, 'default', column_default) ORDER BY table_name, ordinal_position) FROM information_schema.columns WHERE table_schema = 'public'),
  'constraints', (SELECT jsonb_agg(jsonb_build_object('table', c.relname, 'name', k.conname, 'type', k.contype, 'definition', pg_get_constraintdef(k.oid)) ORDER BY c.relname, k.conname) FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public'),
  'indexes', (SELECT jsonb_agg(jsonb_build_object('table', tablename, 'name', indexname, 'definition', indexdef) ORDER BY tablename, indexname) FROM pg_indexes WHERE schemaname = 'public'),
  'triggers', (SELECT jsonb_agg(jsonb_build_object('table', c.relname, 'name', t.tgname, 'enabled', t.tgenabled, 'definition', pg_get_triggerdef(t.oid)) ORDER BY c.relname, t.tgname) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND NOT t.tgisinternal),
  'policies', (SELECT jsonb_agg(to_jsonb(p) ORDER BY tablename, policyname) FROM pg_policies p WHERE schemaname = 'public'),
  'table_grants', (SELECT jsonb_agg(to_jsonb(g) ORDER BY table_name, grantee, privilege_type) FROM information_schema.role_table_grants g WHERE table_schema = 'public'),
  'sequence_grants', (SELECT jsonb_agg(to_jsonb(g) ORDER BY object_name, grantee, privilege_type) FROM information_schema.role_usage_grants g WHERE object_schema = 'public'),
  'sequences', (SELECT jsonb_agg(to_jsonb(s) ORDER BY sequencename) FROM pg_sequences s WHERE schemaname = 'public'),
  'roles_without_passwords', (SELECT jsonb_agg(jsonb_build_object('name', rolname, 'superuser', rolsuper, 'inherit', rolinherit, 'create_role', rolcreaterole, 'create_db', rolcreatedb, 'login', rolcanlogin, 'bypass_rls', rolbypassrls) ORDER BY rolname) FROM pg_roles WHERE rolname NOT LIKE 'pg_%')
));
