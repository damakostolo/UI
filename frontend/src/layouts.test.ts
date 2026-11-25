import { describe,expect,it } from 'vitest';
import { allWidgets, orders } from './layouts';

describe('layout invariants',()=>{
  it('keeps all six actions in every layout',()=>{
    for(const order of Object.values(orders)) expect([...order].sort()).toEqual([...allWidgets].sort());
  });
});
