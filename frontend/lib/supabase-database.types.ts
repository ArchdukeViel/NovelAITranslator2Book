export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      alembic_version: {
        Row: {
          version_num: string
        }
        Insert: {
          version_num: string
        }
        Update: {
          version_num?: string
        }
        Relationships: []
      }
      audit_logs: {
        Row: {
          action: string
          actor_user_id: number | null
          created_at: string
          id: number
          metadata_json: string | null
          target_id: string | null
          target_type: string | null
        }
        Insert: {
          action: string
          actor_user_id?: number | null
          created_at?: string
          id?: number
          metadata_json?: string | null
          target_id?: string | null
          target_type?: string | null
        }
        Update: {
          action?: string
          actor_user_id?: number | null
          created_at?: string
          id?: number
          metadata_json?: string | null
          target_id?: string | null
          target_type?: string | null
        }
        Relationships: []
      }
      chapters: {
        Row: {
          chapter_number: number
          created_at: string
          id: number
          novel_id: number
          raw_status: string
          raw_storage_key: string | null
          source_url: string | null
          title: string | null
          translated_storage_key: string | null
          translation_error: string | null
          translation_state: string
          translation_status: string
          updated_at: string
          word_count: number | null
        }
        Insert: {
          chapter_number: number
          created_at?: string
          id?: number
          novel_id: number
          raw_status: string
          raw_storage_key?: string | null
          source_url?: string | null
          title?: string | null
          translated_storage_key?: string | null
          translation_error?: string | null
          translation_state?: string
          translation_status: string
          updated_at?: string
          word_count?: number | null
        }
        Update: {
          chapter_number?: number
          created_at?: string
          id?: number
          novel_id?: number
          raw_status?: string
          raw_storage_key?: string | null
          source_url?: string | null
          title?: string | null
          translated_storage_key?: string | null
          translation_error?: string | null
          translation_state?: string
          translation_status?: string
          updated_at?: string
          word_count?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "fk_chapters_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
        ]
      }
      crawl_jobs: {
        Row: {
          completed_at: string | null
          created_at: string
          created_by: string | null
          error_message: string | null
          id: number
          novel_id: number | null
          source_url: string | null
          status: string
        }
        Insert: {
          completed_at?: string | null
          created_at?: string
          created_by?: string | null
          error_message?: string | null
          id?: number
          novel_id?: number | null
          source_url?: string | null
          status: string
        }
        Update: {
          completed_at?: string | null
          created_at?: string
          created_by?: string | null
          error_message?: string | null
          id?: number
          novel_id?: number | null
          source_url?: string | null
          status?: string
        }
        Relationships: [
          {
            foreignKeyName: "fk_crawl_jobs_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
        ]
      }
      email_verification_tokens: {
        Row: {
          created_at: string
          expires_at: string
          id: number
          request_ip: string | null
          token_hash: string
          used_at: string | null
          user_agent: string | null
          user_id: number
        }
        Insert: {
          created_at?: string
          expires_at: string
          id?: number
          request_ip?: string | null
          token_hash: string
          used_at?: string | null
          user_agent?: string | null
          user_id: number
        }
        Update: {
          created_at?: string
          expires_at?: string
          id?: number
          request_ip?: string | null
          token_hash?: string
          used_at?: string | null
          user_agent?: string | null
          user_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_email_verification_tokens_user_id_users"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      genres: {
        Row: {
          created_at: string
          display_order: number
          id: number
          is_active: boolean
          is_adult: boolean
          name_en: string | null
          name_ja: string
          slug: string
        }
        Insert: {
          created_at?: string
          display_order?: number
          id?: number
          is_active?: boolean
          is_adult?: boolean
          name_en?: string | null
          name_ja: string
          slug: string
        }
        Update: {
          created_at?: string
          display_order?: number
          id?: number
          is_active?: boolean
          is_adult?: boolean
          name_en?: string | null
          name_ja?: string
          slug?: string
        }
        Relationships: []
      }
      library_items: {
        Row: {
          added_at: string
          novel_id: number
          status: string
          user_id: number
        }
        Insert: {
          added_at?: string
          novel_id: number
          status: string
          user_id: number
        }
        Update: {
          added_at?: string
          novel_id?: number
          status?: string
          user_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_library_items_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_library_items_user_id_users"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      novel_genres: {
        Row: {
          assigned_at: string
          assigned_by: string
          genre_id: number
          novel_id: number
        }
        Insert: {
          assigned_at?: string
          assigned_by?: string
          genre_id: number
          novel_id: number
        }
        Update: {
          assigned_at?: string
          assigned_by?: string
          genre_id?: number
          novel_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_novel_genres_genre_id_genres"
            columns: ["genre_id"]
            isOneToOne: false
            referencedRelation: "genres"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_genres_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
        ]
      }
      novel_glossary_aliases: {
        Row: {
          alias_text: string
          alias_type: string
          applies_to: string | null
          created_at: string
          glossary_entry_id: number
          id: number
          language: string | null
          matching_policy: string | null
          notes: string | null
          novel_id: number
          text_origin: string | null
          updated_at: string
        }
        Insert: {
          alias_text: string
          alias_type?: string
          applies_to?: string | null
          created_at?: string
          glossary_entry_id: number
          id?: number
          language?: string | null
          matching_policy?: string | null
          notes?: string | null
          novel_id: number
          text_origin?: string | null
          updated_at?: string
        }
        Update: {
          alias_text?: string
          alias_type?: string
          applies_to?: string | null
          created_at?: string
          glossary_entry_id?: number
          id?: number
          language?: string | null
          matching_policy?: string | null
          notes?: string | null
          novel_id?: number
          text_origin?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "fk_novel_glossary_aliases_glossary_entry_id_novel_gloss_8b50"
            columns: ["glossary_entry_id"]
            isOneToOne: false
            referencedRelation: "novel_glossary_entries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_aliases_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
        ]
      }
      novel_glossary_decision_events: {
        Row: {
          actor_user_id: number | null
          alias_id: number | null
          created_at: string
          decision_source: string
          event_type: string
          glossary_entry_id: number | null
          id: number
          new_value_json: string | null
          novel_id: number
          old_value_json: string | null
          rationale: string | null
        }
        Insert: {
          actor_user_id?: number | null
          alias_id?: number | null
          created_at?: string
          decision_source?: string
          event_type: string
          glossary_entry_id?: number | null
          id?: number
          new_value_json?: string | null
          novel_id: number
          old_value_json?: string | null
          rationale?: string | null
        }
        Update: {
          actor_user_id?: number | null
          alias_id?: number | null
          created_at?: string
          decision_source?: string
          event_type?: string
          glossary_entry_id?: number | null
          id?: number
          new_value_json?: string | null
          novel_id?: number
          old_value_json?: string | null
          rationale?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "fk_novel_glossary_decision_events_actor_user_id_users"
            columns: ["actor_user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_decision_events_alias_id_novel_glossa_f903"
            columns: ["alias_id"]
            isOneToOne: false
            referencedRelation: "novel_glossary_aliases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_decision_events_glossary_entry_id_nov_9a93"
            columns: ["glossary_entry_id"]
            isOneToOne: false
            referencedRelation: "novel_glossary_entries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_decision_events_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
        ]
      }
      novel_glossary_entries: {
        Row: {
          admin_notes: string | null
          approved_translation: string | null
          canonical_term: string
          confidence: number | null
          created_at: string
          created_by_user_id: number | null
          deprecated_at: string | null
          enforcement_level: string
          first_seen_chapter_id: number | null
          first_seen_chapter_number: number | null
          id: number
          last_seen_chapter_id: number | null
          last_seen_chapter_number: number | null
          matching_policy: string
          novel_id: number | null
          owner_locked: boolean
          public_description: string | null
          public_visible: boolean
          replacement_policy: string
          scope: string
          status: string
          term_type: string
          updated_at: string
          updated_by_user_id: number | null
        }
        Insert: {
          admin_notes?: string | null
          approved_translation?: string | null
          canonical_term: string
          confidence?: number | null
          created_at?: string
          created_by_user_id?: number | null
          deprecated_at?: string | null
          enforcement_level?: string
          first_seen_chapter_id?: number | null
          first_seen_chapter_number?: number | null
          id?: number
          last_seen_chapter_id?: number | null
          last_seen_chapter_number?: number | null
          matching_policy?: string
          novel_id?: number | null
          owner_locked?: boolean
          public_description?: string | null
          public_visible?: boolean
          replacement_policy?: string
          scope?: string
          status?: string
          term_type: string
          updated_at?: string
          updated_by_user_id?: number | null
        }
        Update: {
          admin_notes?: string | null
          approved_translation?: string | null
          canonical_term?: string
          confidence?: number | null
          created_at?: string
          created_by_user_id?: number | null
          deprecated_at?: string | null
          enforcement_level?: string
          first_seen_chapter_id?: number | null
          first_seen_chapter_number?: number | null
          id?: number
          last_seen_chapter_id?: number | null
          last_seen_chapter_number?: number | null
          matching_policy?: string
          novel_id?: number | null
          owner_locked?: boolean
          public_description?: string | null
          public_visible?: boolean
          replacement_policy?: string
          scope?: string
          status?: string
          term_type?: string
          updated_at?: string
          updated_by_user_id?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "fk_novel_glossary_entries_created_by_user_id_users"
            columns: ["created_by_user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_entries_first_seen_chapter_id_chapters"
            columns: ["first_seen_chapter_id"]
            isOneToOne: false
            referencedRelation: "chapters"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_entries_last_seen_chapter_id_chapters"
            columns: ["last_seen_chapter_id"]
            isOneToOne: false
            referencedRelation: "chapters"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_entries_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_entries_updated_by_user_id_users"
            columns: ["updated_by_user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      novel_glossary_qa_findings: {
        Row: {
          chapter_id: number | null
          context_ref: string | null
          created_at: string
          finding_type: string
          glossary_entry_id: number | null
          id: number
          matched_text: string | null
          novel_id: number
          resolved_at: string | null
          reviewer_notes: string | null
          reviewer_user_id: number | null
          severity: string
          status: string
          suggested_text: string | null
        }
        Insert: {
          chapter_id?: number | null
          context_ref?: string | null
          created_at?: string
          finding_type: string
          glossary_entry_id?: number | null
          id?: number
          matched_text?: string | null
          novel_id: number
          resolved_at?: string | null
          reviewer_notes?: string | null
          reviewer_user_id?: number | null
          severity?: string
          status?: string
          suggested_text?: string | null
        }
        Update: {
          chapter_id?: number | null
          context_ref?: string | null
          created_at?: string
          finding_type?: string
          glossary_entry_id?: number | null
          id?: number
          matched_text?: string | null
          novel_id?: number
          resolved_at?: string | null
          reviewer_notes?: string | null
          reviewer_user_id?: number | null
          severity?: string
          status?: string
          suggested_text?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "fk_novel_glossary_qa_findings_chapter_id_chapters"
            columns: ["chapter_id"]
            isOneToOne: false
            referencedRelation: "chapters"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_qa_findings_glossary_entry_id_novel_g_01f5"
            columns: ["glossary_entry_id"]
            isOneToOne: false
            referencedRelation: "novel_glossary_entries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_qa_findings_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_qa_findings_reviewer_user_id_users"
            columns: ["reviewer_user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      novel_glossary_source_provenance: {
        Row: {
          chapter_id: number | null
          confidence: number | null
          created_at: string
          evidence_quality: string | null
          evidence_ref: string | null
          first_seen_at: string | null
          glossary_entry_id: number | null
          id: number
          last_seen_at: string | null
          local_reference: string | null
          novel_id: number
          observed_translated_term: string | null
          raw_source_term: string | null
          source_adapter: string
          source_chapter_id: string | null
          source_chapter_number: number | null
          source_novel_id: string | null
          source_site: string
          source_url: string | null
          updated_at: string
        }
        Insert: {
          chapter_id?: number | null
          confidence?: number | null
          created_at?: string
          evidence_quality?: string | null
          evidence_ref?: string | null
          first_seen_at?: string | null
          glossary_entry_id?: number | null
          id?: number
          last_seen_at?: string | null
          local_reference?: string | null
          novel_id: number
          observed_translated_term?: string | null
          raw_source_term?: string | null
          source_adapter: string
          source_chapter_id?: string | null
          source_chapter_number?: number | null
          source_novel_id?: string | null
          source_site: string
          source_url?: string | null
          updated_at?: string
        }
        Update: {
          chapter_id?: number | null
          confidence?: number | null
          created_at?: string
          evidence_quality?: string | null
          evidence_ref?: string | null
          first_seen_at?: string | null
          glossary_entry_id?: number | null
          id?: number
          last_seen_at?: string | null
          local_reference?: string | null
          novel_id?: number
          observed_translated_term?: string | null
          raw_source_term?: string | null
          source_adapter?: string
          source_chapter_id?: string | null
          source_chapter_number?: number | null
          source_novel_id?: string | null
          source_site?: string
          source_url?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "fk_novel_glossary_source_provenance_chapter_id_chapters"
            columns: ["chapter_id"]
            isOneToOne: false
            referencedRelation: "chapters"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_source_provenance_glossary_entry_id_n_eb2c"
            columns: ["glossary_entry_id"]
            isOneToOne: false
            referencedRelation: "novel_glossary_entries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_glossary_source_provenance_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
        ]
      }
      novel_requests: {
        Row: {
          approved_novel_id: number | null
          created_at: string
          id: number
          novel_id: number | null
          rejection_reason: string | null
          request_type: string
          resolved_at: string | null
          source_url: string | null
          status: string
          updated_at: string
          user_id: number | null
        }
        Insert: {
          approved_novel_id?: number | null
          created_at?: string
          id?: number
          novel_id?: number | null
          rejection_reason?: string | null
          request_type: string
          resolved_at?: string | null
          source_url?: string | null
          status: string
          updated_at?: string
          user_id?: number | null
        }
        Update: {
          approved_novel_id?: number | null
          created_at?: string
          id?: number
          novel_id?: number | null
          rejection_reason?: string | null
          request_type?: string
          resolved_at?: string | null
          source_url?: string | null
          status?: string
          updated_at?: string
          user_id?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "fk_novel_requests_approved_novel_id_novels"
            columns: ["approved_novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_requests_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_requests_user_id_users"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      novel_tags: {
        Row: {
          assigned_at: string
          assigned_by: string
          novel_id: number
          origin: string
          tag_id: number
        }
        Insert: {
          assigned_at?: string
          assigned_by?: string
          novel_id: number
          origin?: string
          tag_id: number
        }
        Update: {
          assigned_at?: string
          assigned_by?: string
          novel_id?: number
          origin?: string
          tag_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_novel_tags_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_novel_tags_tag_id_tags"
            columns: ["tag_id"]
            isOneToOne: false
            referencedRelation: "tags"
            referencedColumns: ["id"]
          },
        ]
      }
      novels: {
        Row: {
          author: string | null
          chapter_count: number
          cover_storage_key: string | null
          created_at: string
          glossary_revision: number
          glossary_status: string
          id: number
          is_published: boolean
          language: string
          latest_chapter_id: string | null
          latest_chapter_number: number | null
          latest_chapter_title: string | null
          latest_chapter_updated_at: string | null
          original_title: string | null
          publication_status: string
          slug: string
          source_site: string | null
          source_updated_at: string | null
          source_url: string | null
          status: string
          synopsis: string | null
          title: string
          translated_count: number
          updated_at: string
        }
        Insert: {
          author?: string | null
          chapter_count?: number
          cover_storage_key?: string | null
          created_at?: string
          glossary_revision?: number
          glossary_status?: string
          id?: number
          is_published: boolean
          language: string
          latest_chapter_id?: string | null
          latest_chapter_number?: number | null
          latest_chapter_title?: string | null
          latest_chapter_updated_at?: string | null
          original_title?: string | null
          publication_status?: string
          slug: string
          source_site?: string | null
          source_updated_at?: string | null
          source_url?: string | null
          status: string
          synopsis?: string | null
          title: string
          translated_count?: number
          updated_at?: string
        }
        Update: {
          author?: string | null
          chapter_count?: number
          cover_storage_key?: string | null
          created_at?: string
          glossary_revision?: number
          glossary_status?: string
          id?: number
          is_published?: boolean
          language?: string
          latest_chapter_id?: string | null
          latest_chapter_number?: number | null
          latest_chapter_title?: string | null
          latest_chapter_updated_at?: string | null
          original_title?: string | null
          publication_status?: string
          slug?: string
          source_site?: string | null
          source_updated_at?: string | null
          source_url?: string | null
          status?: string
          synopsis?: string | null
          title?: string
          translated_count?: number
          updated_at?: string
        }
        Relationships: []
      }
      password_reset_tokens: {
        Row: {
          created_at: string
          expires_at: string
          id: number
          request_ip: string | null
          token_hash: string
          used_at: string | null
          user_agent: string | null
          user_id: number
        }
        Insert: {
          created_at?: string
          expires_at: string
          id?: number
          request_ip?: string | null
          token_hash: string
          used_at?: string | null
          user_agent?: string | null
          user_id: number
        }
        Update: {
          created_at?: string
          expires_at?: string
          id?: number
          request_ip?: string | null
          token_hash?: string
          used_at?: string | null
          user_agent?: string | null
          user_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_password_reset_tokens_user_id_users"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      provider_credentials: {
        Row: {
          created_at: string
          encrypted_api_key: string
          id: number
          is_active: boolean
          key_fingerprint: string
          label: string
          last_validated_at: string | null
          last4: string
          model: string | null
          notes: string | null
          provider: string
          updated_at: string
          validation_message: string | null
          validation_status: string
        }
        Insert: {
          created_at?: string
          encrypted_api_key: string
          id?: number
          is_active: boolean
          key_fingerprint: string
          label: string
          last_validated_at?: string | null
          last4: string
          model?: string | null
          notes?: string | null
          provider: string
          updated_at?: string
          validation_message?: string | null
          validation_status: string
        }
        Update: {
          created_at?: string
          encrypted_api_key?: string
          id?: number
          is_active?: boolean
          key_fingerprint?: string
          label?: string
          last_validated_at?: string | null
          last4?: string
          model?: string | null
          notes?: string | null
          provider?: string
          updated_at?: string
          validation_message?: string | null
          validation_status?: string
        }
        Relationships: []
      }
      provider_requests: {
        Row: {
          cost_estimate: number | null
          created_at: string
          error_message: string | null
          id: number
          input_tokens: number | null
          job_id: number | null
          latency_ms: number | null
          output_tokens: number | null
          provider_key: string | null
          provider_model: string | null
          request_id: string | null
          status: string
        }
        Insert: {
          cost_estimate?: number | null
          created_at?: string
          error_message?: string | null
          id?: number
          input_tokens?: number | null
          job_id?: number | null
          latency_ms?: number | null
          output_tokens?: number | null
          provider_key?: string | null
          provider_model?: string | null
          request_id?: string | null
          status: string
        }
        Update: {
          cost_estimate?: number | null
          created_at?: string
          error_message?: string | null
          id?: number
          input_tokens?: number | null
          job_id?: number | null
          latency_ms?: number | null
          output_tokens?: number | null
          provider_key?: string | null
          provider_model?: string | null
          request_id?: string | null
          status?: string
        }
        Relationships: [
          {
            foreignKeyName: "fk_provider_requests_job_id_translation_jobs"
            columns: ["job_id"]
            isOneToOne: false
            referencedRelation: "translation_jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      reading_history: {
        Row: {
          chapter_id: number | null
          id: number
          novel_id: number
          read_at: string
          user_id: number
        }
        Insert: {
          chapter_id?: number | null
          id?: number
          novel_id: number
          read_at?: string
          user_id: number
        }
        Update: {
          chapter_id?: number | null
          id?: number
          novel_id?: number
          read_at?: string
          user_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_reading_history_chapter_id_chapters"
            columns: ["chapter_id"]
            isOneToOne: false
            referencedRelation: "chapters"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_reading_history_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_reading_history_user_id_users"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      reading_progress: {
        Row: {
          chapter_id: number | null
          novel_id: number
          progress_percent: number
          updated_at: string
          user_id: number
        }
        Insert: {
          chapter_id?: number | null
          novel_id: number
          progress_percent: number
          updated_at?: string
          user_id: number
        }
        Update: {
          chapter_id?: number | null
          novel_id?: number
          progress_percent?: number
          updated_at?: string
          user_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_reading_progress_chapter_id_chapters"
            columns: ["chapter_id"]
            isOneToOne: false
            referencedRelation: "chapters"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_reading_progress_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_reading_progress_user_id_users"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      reviews: {
        Row: {
          body: string | null
          created_at: string
          id: number
          novel_id: number
          rating: number | null
          user_id: number
        }
        Insert: {
          body?: string | null
          created_at?: string
          id?: number
          novel_id: number
          rating?: number | null
          user_id: number
        }
        Update: {
          body?: string | null
          created_at?: string
          id?: number
          novel_id?: number
          rating?: number | null
          user_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_reviews_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_reviews_user_id_users"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      scheduler_runtime_states: {
        Row: {
          consecutive_failures: number
          cooldown_until: string | null
          created_at: string
          error_category: string | null
          error_message: string | null
          exhausted_until: string | null
          expires_at: string | null
          failure_count: number
          heartbeat_at: string | null
          id: number
          last_attempt_at: string | null
          last_failure_at: string | null
          last_finished_at: string | null
          last_started_at: string | null
          last_success_at: string | null
          locked_by: string | null
          metadata_json: string | null
          next_eligible_at: string | null
          reason: string | null
          scheduler_key: string
          scope_key: string
          scope_type: string
          state: string
          updated_at: string
        }
        Insert: {
          consecutive_failures?: number
          cooldown_until?: string | null
          created_at?: string
          error_category?: string | null
          error_message?: string | null
          exhausted_until?: string | null
          expires_at?: string | null
          failure_count?: number
          heartbeat_at?: string | null
          id?: number
          last_attempt_at?: string | null
          last_failure_at?: string | null
          last_finished_at?: string | null
          last_started_at?: string | null
          last_success_at?: string | null
          locked_by?: string | null
          metadata_json?: string | null
          next_eligible_at?: string | null
          reason?: string | null
          scheduler_key: string
          scope_key: string
          scope_type: string
          state?: string
          updated_at?: string
        }
        Update: {
          consecutive_failures?: number
          cooldown_until?: string | null
          created_at?: string
          error_category?: string | null
          error_message?: string | null
          exhausted_until?: string | null
          expires_at?: string | null
          failure_count?: number
          heartbeat_at?: string | null
          id?: number
          last_attempt_at?: string | null
          last_failure_at?: string | null
          last_finished_at?: string | null
          last_started_at?: string | null
          last_success_at?: string | null
          locked_by?: string | null
          metadata_json?: string | null
          next_eligible_at?: string | null
          reason?: string | null
          scheduler_key?: string
          scope_key?: string
          scope_type?: string
          state?: string
          updated_at?: string
        }
        Relationships: []
      }
      system_settings: {
        Row: {
          key: string
          updated_at: string
          updated_by: number | null
          value_json: string | null
        }
        Insert: {
          key: string
          updated_at?: string
          updated_by?: number | null
          value_json?: string | null
        }
        Update: {
          key?: string
          updated_at?: string
          updated_by?: number | null
          value_json?: string | null
        }
        Relationships: []
      }
      tags: {
        Row: {
          created_at: string
          id: number
          is_adult: boolean
          name: string
          name_ja: string | null
          updated_at: string
        }
        Insert: {
          created_at?: string
          id?: number
          is_adult?: boolean
          name: string
          name_ja?: string | null
          updated_at?: string
        }
        Update: {
          created_at?: string
          id?: number
          is_adult?: boolean
          name?: string
          name_ja?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      translation_jobs: {
        Row: {
          chapter_id: number | null
          completed_at: string | null
          created_at: string
          created_by: string | null
          error_message: string | null
          estimated_cost: number | null
          id: number
          novel_id: number | null
          provider_key: string | null
          provider_model: string | null
          status: string
          token_input: number | null
          token_output: number | null
        }
        Insert: {
          chapter_id?: number | null
          completed_at?: string | null
          created_at?: string
          created_by?: string | null
          error_message?: string | null
          estimated_cost?: number | null
          id?: number
          novel_id?: number | null
          provider_key?: string | null
          provider_model?: string | null
          status: string
          token_input?: number | null
          token_output?: number | null
        }
        Update: {
          chapter_id?: number | null
          completed_at?: string | null
          created_at?: string
          created_by?: string | null
          error_message?: string | null
          estimated_cost?: number | null
          id?: number
          novel_id?: number | null
          provider_key?: string | null
          provider_model?: string | null
          status?: string
          token_input?: number | null
          token_output?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "fk_translation_jobs_chapter_id_chapters"
            columns: ["chapter_id"]
            isOneToOne: false
            referencedRelation: "chapters"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_translation_jobs_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
        ]
      }
      user_glossary_display_overrides: {
        Row: {
          created_at: string
          display_term: string
          enabled: boolean
          glossary_entry_id: number
          id: number
          novel_id: number
          updated_at: string
          user_id: number
        }
        Insert: {
          created_at?: string
          display_term: string
          enabled?: boolean
          glossary_entry_id: number
          id?: number
          novel_id: number
          updated_at?: string
          user_id: number
        }
        Update: {
          created_at?: string
          display_term?: string
          enabled?: boolean
          glossary_entry_id?: number
          id?: number
          novel_id?: number
          updated_at?: string
          user_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "fk_user_glossary_display_overrides_glossary_entry_id_no_c38d"
            columns: ["glossary_entry_id"]
            isOneToOne: false
            referencedRelation: "novel_glossary_entries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_user_glossary_display_overrides_novel_id_novels"
            columns: ["novel_id"]
            isOneToOne: false
            referencedRelation: "novels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fk_user_glossary_display_overrides_user_id_users"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      users: {
        Row: {
          auth_provider: string | null
          auth_provider_subject: string | null
          created_at: string
          display_name: string | null
          email: string
          email_verified_at: string | null
          id: number
          is_active: boolean
          last_login_at: string | null
          password_hash: string | null
          role: string
        }
        Insert: {
          auth_provider?: string | null
          auth_provider_subject?: string | null
          created_at?: string
          display_name?: string | null
          email: string
          email_verified_at?: string | null
          id?: number
          is_active: boolean
          last_login_at?: string | null
          password_hash?: string | null
          role: string
        }
        Update: {
          auth_provider?: string | null
          auth_provider_subject?: string | null
          created_at?: string
          display_name?: string | null
          email?: string
          email_verified_at?: string | null
          id?: number
          is_active?: boolean
          last_login_at?: string | null
          password_hash?: string | null
          role?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      current_user_id: { Args: never; Returns: number }
      is_owner: { Args: never; Returns: boolean }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
