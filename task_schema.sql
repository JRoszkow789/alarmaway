drop table if exists task_index;
create table job_index (
	job_id int unsigned not null auto_increment,
	job_parent int unsigned not null,
	job_task_id varchar(60) not null,
	primary key (job_id)
);
