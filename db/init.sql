CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT
);

CREATE TABLE petani (
    id SERIAL PRIMARY KEY,
    nama TEXT,
    nik VARCHAR(20),
    tanggal_lahir DATE,
    no_telpon VARCHAR(15),
    alamat TEXT,
    geom GEOMETRY(POINT, 4326),
    id_user INTEGER REFERENCES users(id)
);

CREATE TABLE lahan (
    id SERIAL PRIMARY KEY,
    id_petani INTEGER REFERENCES petani(id),
    luas_lahan DOUBLE PRECISION,
    geom GEOMETRY(MULTIPOLYGON, 4326)
);