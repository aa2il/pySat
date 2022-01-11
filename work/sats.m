close all
clear all

fname='satellites.log_jo97_ao91'

% Becoming painfully obvious that octave doesn't handle this type of data very well

%data=dlmread(fname,',');        % Seems to only like numeric data
#data=textread(fname,'%s');       %
#data=textscan(fname,'%s');       %
#data=fileread(fname);       %  Reads everything into a giant string
data=importdata(fname);       %  

size(data)
data(1)
data(1:10)

hdr=strsplit(cell2mat(data(1)),',')
nrows=length(data)
ncols=length(hdr)
c=cell(nrows,ncols);
for i=1:(nrows-1)
  a=strsplit(cell2mat(data(i+1)),',');
  for j=1:ncols
    c(i,j)=a(j);
  end
end

size(c)
c(1,:)
c(2,:)

