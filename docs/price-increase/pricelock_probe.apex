// Rollback probe: can automation create a Revenue Enhancement opp the way the Price Escalation button would?
Account a = [SELECT Id, Name, OwnerId, Client_Success_Rep_2__c FROM Account WHERE Id = '0010f00002KTyDcAAL'];
Id stdRt = [SELECT Id FROM RecordType WHERE SobjectType='Opportunity' AND DeveloperName='Standard_Opportunity' LIMIT 1].Id;
Savepoint sp = Database.setSavepoint();
// Attempt 1: minimal fields, as a flow would pre-fill them
Opportunity o = new Opportunity(Name = 'ZZ TEST PROBE Price Increase 2027 (rollback)', AccountId = a.Id, RecordTypeId = stdRt,
    Type = 'Revenue Enhancement', StageName = 'Discovery', CloseDate = Date.today().addMonths(3), Amount = 2953.20,
    LeadSource = 'AE Prospecting', ForecastCategoryName = 'Pipeline', NextStep = 'Send 60-day notice', Description = 'Created by Price Escalation probe');
Database.SaveResult r1 = Database.insert(o, false);
System.debug('A1 minimal insert success=' + r1.isSuccess());
for (Database.Error e : r1.getErrors()) System.debug('A1 ERR ' + e.getStatusCode() + ' ' + e.getFields() + ' ' + e.getMessage());
if (r1.isSuccess()) {
    // Attempt 2: move straight to Contract, then Closed Won, to list every gate the rep would hit
    o.StageName = 'Contract'; o.NextStep = 'Signed';
    Database.SaveResult r2 = Database.update(o, false);
    System.debug('A2 to Contract success=' + r2.isSuccess());
    for (Database.Error e : r2.getErrors()) System.debug('A2 ERR ' + e.getStatusCode() + ' ' + e.getFields() + ' ' + e.getMessage());
    o.StageName = 'Closed Won'; o.NextStep = 'Done'; o.Why_Passport__c = 'probe';
    Database.SaveResult r3 = Database.update(o, false);
    System.debug('A3 to Closed Won success=' + r3.isSuccess());
    for (Database.Error e : r3.getErrors()) System.debug('A3 ERR ' + e.getStatusCode() + ' ' + e.getFields() + ' ' + e.getMessage());
    // Task for the CS rep, as the weekly flow would create
    Task t = new Task(Subject = 'Price increase notice due', WhatId = a.Id, OwnerId = (a.Client_Success_Rep_2__c != null ? a.Client_Success_Rep_2__c : a.OwnerId), ActivityDate = Date.today().addDays(14), Status = 'Not Started', Priority = 'Normal');
    Database.SaveResult r4 = Database.insert(t, false);
    System.debug('A4 task insert success=' + r4.isSuccess() + ' ownerIsCSRep=' + (a.Client_Success_Rep_2__c != null));
    for (Database.Error e : r4.getErrors()) System.debug('A4 ERR ' + e.getMessage());
}
System.debug('LIMITS soql=' + Limits.getQueries() + '/' + Limits.getLimitQueries() + ' dml=' + Limits.getDmlStatements() + ' cpu=' + Limits.getCpuTime());
Database.rollback(sp);
System.debug('ROLLED BACK');
