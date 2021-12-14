-- migrate:up

CREATE TABLE wikis (
    id integer PRIMARY KEY,
    url text UNIQUE NOT NULL,
    last_check_time timestamp
);

CREATE TABLE transports (
    wiki_id integer NOT NULL REFERENCES wikis(id),
    type text NOT NULL,
    url text,
    actions integer
)

-- migrate:down

