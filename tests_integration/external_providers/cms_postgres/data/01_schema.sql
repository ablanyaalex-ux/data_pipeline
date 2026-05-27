-- Original table definition script from postgres (PGAdmin4)
-- Added: extension, schema, sequence (so CREATE TABLE works in a clean container)


-- hstore type support
--NOTE(glo): hstore is not enabled by default in Postgres but is required for `initial_message` (legacy key–value column); explicitly create extension so table can be created in a fresh container.
CREATE EXTENSION IF NOT EXISTS hstore;

-- schema (public usually exists, but safe)
CREATE SCHEMA IF NOT EXISTS public;

-- sequence used by id default
CREATE SEQUENCE IF NOT EXISTS public.tasks_id_seq;


CREATE TABLE public.tasks (
  id bigint NOT NULL DEFAULT nextval('tasks_id_seq'::regclass),
  title character varying,
  description text,
  parent_guid character varying,
  assignee_guid character varying,
  assigned_at timestamp without time zone,
  completed_at timestamp without time zone,
  initial_message hstore DEFAULT ''::hstore,
  created_at timestamp without time zone NOT NULL,
  updated_at timestamp without time zone NOT NULL,
  complaint_reference character varying,
  parent_type character varying,
  status character varying DEFAULT 'new'::character varying,
  guide_guid character varying,
  completed_by character varying,
  handler character varying,
  expired_at timestamp without time zone,
  milestones text[] NOT NULL DEFAULT '{}'::text[],
  current_milestone integer NOT NULL DEFAULT 0,
  complaint_guid character varying,
  adr_guid character varying,
  paused_at timestamp without time zone,
  visible boolean DEFAULT true,
  permitted_users_arr integer[] DEFAULT '{}'::integer[],
  permitted_roles_arr text[] DEFAULT '{}'::text[],
  complaint_status character varying,
  scheduled_datetime timestamp without time zone,
  due_date date,
  counter integer,
  type_id bigint NOT NULL
);
