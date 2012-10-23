set foreign_key_checks = 0;
drop table if exists job_batch;
drop table if exists job_log;
drop table if exists aa_things;
drop table if exists user_properties;
drop table if exists alarm_calls;
drop table if exists alarm_call;
drop table if exists users;
create table users (
	user_id int unsigned not null auto_increment,
	user_email varchar(120) not null unique,
	user_pw varchar(165) not null,
	user_register timestamp not null default current_timestamp,
	user_status tinyint unsigned not null,
	user_role tinyint unsigned not null,
	primary key (user_id)
);
drop table if exists alarms;
create table alarms (
	alarm_id int unsigned not null auto_increment,
	alarm_owner int unsigned not null,
	alarm_phone int unsigned not null,
	alarm_time time not null,
	alarm_active tinyint unsigned not null default 0,
	alarm_created timestamp not null default current_timestamp,
	primary key (alarm_id)
);
alter table alarms
add constraint fk_alarm_owner
foreign key (alarm_owner) references users(user_id)
on update cascade
on delete cascade;
alter table alarms
add constraint fk_alarm_phone
foreign key (alarm_phone) references user_phones(phone_id)
on update cascade
on delete cascade;
drop table if exists user_phones;
create table user_phones (
	phone_id int unsigned not null auto_increment,
	phone_owner int unsigned not null,
	phone_number char(10) not null unique,
	phone_verified tinyint unsigned not null default 0,
	phone_added timestamp not null default current_timestamp,
	primary key (phone_id)
);
alter table user_phones
add constraint fk_phone_owner
foreign key (phone_owner) references users(user_id)
on update cascade
on delete cascade;
drop table if exists alarm_events;
create table alarm_events (
	event_id int unsigned not null auto_increment,
	event_owner int unsigned not null,
	event_start timestamp not null default current_timestamp,
	event_end timestamp null,
	event_status tinyint unsigned not null,
	event_call_count tinyint unsigned not null default 0,
	event_msg_count tinyint unsigned not null default 0,
	primary key (event_id)
);
alter table alarm_events
add constraint fk_event_owner
foreign key (event_owner) references alarms(alarm_id)
on update cascade
on delete cascade;
drop table if exists responses;
create table responses (
	response_id int unsigned not null auto_increment,
	response_recieved timestamp not null default current_timestamp,
	response_from char(10) not null,
	response_msg varchar(255) not null,
	primary key (response_id)
);
set foreign_key_checks = 1;
