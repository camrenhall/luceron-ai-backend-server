create table public.agent_context (
  context_id uuid not null default gen_random_uuid (),
  case_id uuid not null,
  agent_type public.agent_type not null,
  context_key character varying(255) not null,
  context_value jsonb not null,
  expires_at timestamp with time zone null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint agent_context_pkey primary key (context_id),
  constraint unique_case_agent_context unique (case_id, agent_type, context_key),
  constraint agent_context_case_id_fkey foreign KEY (case_id) references cases (case_id) on delete CASCADE
) TABLESPACE pg_default;

create table public.agent_conversations (
  conversation_id uuid not null default gen_random_uuid (),
  agent_type public.agent_type not null,
  status public.conversation_status null default 'ACTIVE'::conversation_status,
  total_tokens_used integer null default 0,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint agent_conversations_pkey primary key (conversation_id)
) TABLESPACE pg_default;

create table public.agent_messages (
  message_id uuid not null default gen_random_uuid (),
  conversation_id uuid not null,
  role public.message_role not null,
  content jsonb not null,
  total_tokens integer null,
  model_used character varying(100) not null,
  function_name character varying(255) null,
  function_arguments jsonb null,
  function_response jsonb null,
  created_at timestamp with time zone not null default now(),
  sequence_number integer not null,
  constraint agent_messages_pkey primary key (message_id),
  constraint unique_conversation_sequence unique (conversation_id, sequence_number),
  constraint agent_messages_conversation_id_fkey foreign KEY (conversation_id) references agent_conversations (conversation_id) on delete CASCADE
) TABLESPACE pg_default;

create table public.agent_summaries (
  summary_id uuid not null default gen_random_uuid (),
  conversation_id uuid not null,
  last_message_id uuid null,
  summary_content text not null,
  messages_summarized integer not null default 0,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint agent_summaries_pkey primary key (summary_id),
  constraint agent_summaries_conversation_id_fkey foreign KEY (conversation_id) references agent_conversations (conversation_id) on delete CASCADE,
  constraint agent_summaries_last_message_id_fkey foreign KEY (last_message_id) references agent_messages (message_id) on delete set null
) TABLESPACE pg_default;

create table public.cases (
  client_email character varying(255) not null,
  client_name character varying(255) not null,
  created_at timestamp with time zone null default now(),
  client_phone character varying(25) null,
  case_id uuid not null default extensions.uuid_generate_v4 (),
  status public.case_status not null default 'OPEN'::case_status,
  constraint cases_pkey primary key (case_id)
) TABLESPACE pg_default;

create table public.client_communications (
  communication_id uuid not null default gen_random_uuid (),
  channel public.communication_channel not null,
  direction public.communication_direction not null,
  status public.delivery_status not null default 'sent'::delivery_status,
  opened_at timestamp with time zone null,
  sender character varying(255) not null,
  recipient character varying(255) not null,
  subject text null,
  message_content text not null,
  created_at timestamp with time zone not null default now(),
  sent_at timestamp with time zone null,
  resend_id character varying(255) null,
  case_id uuid not null,
  constraint client_communications_pkey primary key (communication_id),
  constraint client_communications_case_id_fkey foreign KEY (case_id) references cases (case_id)
) TABLESPACE pg_default;

create table public.document_analysis (
  analysis_content text not null,
  analysis_status character varying(20) null default 'completed'::character varying,
  model_used character varying(50) not null,
  tokens_used integer null,
  analyzed_at timestamp without time zone not null default now(),
  created_at timestamp without time zone not null default now(),
  analysis_id uuid not null default extensions.uuid_generate_v4 (),
  document_id uuid not null,
  case_id uuid not null,
  analysis_reasoning text null,
  context_summary_created boolean not null default false,
  constraint document_analysis_pkey primary key (analysis_id),
  constraint fk_document_analysis_case foreign KEY (case_id) references cases (case_id) on delete CASCADE,
  constraint fk_document_analysis_document foreign KEY (document_id) references documents (document_id) on delete CASCADE,
  constraint document_analysis_analysis_status_check check (
    (
      (analysis_status)::text = any (
        array[
          ('PENDING'::character varying)::text,
          ('PROCESSING'::character varying)::text,
          ('COMPLETED'::character varying)::text,
          ('FAILED'::character varying)::text
        ]
      )
    )
  )
) TABLESPACE pg_default;

create table public.documents (
  original_file_name character varying(500) not null,
  original_file_size bigint not null,
  original_file_type character varying(100) not null,
  original_s3_location text not null,
  original_s3_key character varying(1000) not null,
  status character varying(20) null default 'PENDING'::character varying,
  created_at timestamp without time zone not null default now(),
  document_id uuid not null default extensions.uuid_generate_v4 (),
  case_id uuid not null,
  processed_file_name character varying(500) null,
  processed_file_size bigint null,
  processed_s3_location text null,
  processed_s3_key character varying(1000) null,
  batch_id character varying(255) null,
  constraint documents_pkey primary key (document_id),
  constraint fk_documents_case foreign KEY (case_id) references cases (case_id) on delete CASCADE,
  constraint documents_status_check check (
    (
      (status)::text = any (
        array[
          ('PENDING'::character varying)::text,
          ('PROCESSING'::character varying)::text,
          ('COMPLETED'::character varying)::text,
          ('FAILED'::character varying)::text
        ]
      )
    )
  )
) TABLESPACE pg_default;

create table public.error_logs (
  error_id uuid not null default extensions.uuid_generate_v4 (),
  component character varying(255) not null,
  error_message text not null,
  severity character varying(50) not null default 'medium'::character varying,
  context jsonb null,
  email_sent boolean not null default false,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint error_logs_pkey primary key (error_id)
) TABLESPACE pg_default;