drop table if exists users;
create table users (
	user_id mediumint unsigned not null auto_increment,
	primary_phone char(10) unique not null,
	join_date timestamp not null default current_timestamp,
	email varchar(120) unique,
	pw_hash varchar(165),
	primary key (user_id)
);

drop table if exists alarms;
create table alarms (
	alarm_id int unsigned not null auto_increment,
	active tinyint(1) not null,
	created_date timestamp not null default current_timestamp,
	alarm_time time not null,
	parent_id mediumint unsigned not null,
	primary key (alarm_id),
	foreign key (parent_id) references users (user_id)
);
