import test from 'node:test';
import assert from 'node:assert/strict';
import { Conversations } from '../conversations.js';
test('context is scoped to a tab and expires after inactivity', () => {
  const conversations = new Conversations(300000);
  conversations.set('owner:tab1', 'ha-one', 0);
  assert.equal(conversations.get('owner:tab1', 299999), 'ha-one');
  assert.equal(conversations.get('owner:tab2', 1), undefined);
  assert.equal(conversations.get('other:tab1', 1), undefined);
  assert.equal(conversations.get('owner:tab1', 300000), undefined);
});
test('a completed follow-up extends its context lifetime', () => {
  const conversations = new Conversations(100);
  conversations.set('tab', 'ha-one', 0);
  conversations.set('tab', 'ha-one', 90);
  assert.equal(conversations.get('tab', 150), 'ha-one');
  assert.equal(conversations.get('tab', 190), undefined);
});
