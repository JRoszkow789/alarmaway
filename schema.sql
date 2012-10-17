drop table if exists users;
create table users (
	user_id int unsigned not null auto_increment,
	user_pw varchar(165) not null,
	user_register timestamp not null default current_timestamp,
	user_status tinyint unsigned not null,
	user_role tinyint unsigned not null,
	primary key (user_id)
);
drop table if exists user_properties;
create table user_properties (
	up_user int unsigned not null,
	up_property varchar(63) not null,
	up_value varchar(255) not null,
	primary key (up_user, up_property)
);
alter table user_properties
add constraint fk_up_user
foreign key (up_user) references users(user_id)
on update cascade
on delete cascade;
drop table if exists alarms;
create table alarms (
	alarm_id int unsigned not null auto_increment,
	alarm_user int unsigned not null,
	alarm_status tinyint unsigned not null,
	alarm_created timestamp not null default current_timestamp,
	alarm_ended timestamp null,
	primary key (alarm_id)
);
alter table alarms
add constraint fk_alarm_user
foreign key (alarm_user) references users(user_id)
on update cascade
on delete cascade;
drop table if exists alarm_call;
create table alarm_call (
	ac_id int unsigned not null auto_increment,
	ac_user int unsigned not null,
	ac_alarm int unsigned not null,
	ac_started timestamp not null default current_timestamp,
	ac_ended timestamp null,
	ac_status tinyint unsigned not null,
	ac_reason tinyint unsigned not null,
	primary key (ac_id)
);
alter table alarm_call
add constraint fk_ac_user
foreign key (ac_user) references users(user_id)
on update cascade
on delete cascade;
alter table alarm_call
add constraint fk_ac_alarm
foreign key (ac_alarm) references alarms(alarm_id)
on update cascade
on delete cascade;
drop table if exists job_batch;
create table job_batch (
	batch_id int unsigned not null auto_increment,
	batch_alarm_call int unsigned not null,
	batch_started timestamp not null default current_timestamp,
	batch_ended timestamp null,
	batch_status tinyint unsigned not null,
	primary key (batch_id)
);
alter table job_batch
add constraint fk_batch_alarm_call
foreign key (batch_alarm_call) references alarm_call(ac_id)
on update cascade
on delete cascade;
drop table if exists job_log;
create table job_log (
	jl_entry_id int unsigned not null auto_increment,
	jl_user int unsigned not null,
	jl_alarm_call int unsigned not null,
	jl_batch int unsigned not null,
	jl_job int unsigned not null,
	jl_entry_created timestamp not null default current_timestamp,
	primary key (jl_entry_id)
);
alter table job_log
add constraint fk_jl_user
foreign key (jl_user) references users(user_id)
on update cascade
on delete cascade;
alter table job_log
add constraint fk_jl_alarm_call
foreign key (jl_alarm_call) references alarm_call(ac_id)
on update cascade
on delete cascade;
alter table job_log
add constraint fk_jl_batch
foreign key (jl_batch) references job_batch(batch_id)
on update cascade
on delete cascade;
