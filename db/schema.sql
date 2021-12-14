SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying(255) NOT NULL
);


--
-- Name: transports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transports (
    wiki_id integer NOT NULL,
    type text NOT NULL,
    url text,
    actions integer
);


--
-- Name: wikis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wikis (
    id integer NOT NULL,
    url text NOT NULL,
    last_check_time timestamp without time zone
);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: wikis wikis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wikis
    ADD CONSTRAINT wikis_pkey PRIMARY KEY (id);


--
-- Name: wikis wikis_url_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wikis
    ADD CONSTRAINT wikis_url_key UNIQUE (url);


--
-- Name: transports transports_wiki_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transports
    ADD CONSTRAINT transports_wiki_id_fkey FOREIGN KEY (wiki_id) REFERENCES public.wikis(id);


--
-- PostgreSQL database dump complete
--


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20211210211314');
