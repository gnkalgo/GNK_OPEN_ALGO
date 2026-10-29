import { ledger } from "./ledger";
import type { Order } from "./paper";
const fill = (side: "BUY" | "SELL", quantity: number, price: number, product = "Delivery", status: Order["status"] = "Filled"): Order =>
  ({id:crypto.randomUUID(),symbol:"RELIANCE",exchange:"NSE",product,side,quantity,price,status,time:"fixture",type:"LIMIT"});
test("average cost handles partial close and reversals without mixing products", () => {
  const chronological = [fill("BUY",10,100),fill("SELL",4,120),fill("SELL",8,90),fill("BUY",1,80),fill("BUY",5,70,"Intraday"),fill("BUY",100,1,"Delivery","Rejected")];
  const [delivery,intraday] = ledger(chronological.reverse(),[{symbol:"RELIANCE",price:100}]);
  expect(delivery).toMatchObject({quantity:-1,average:90,realized:30,pnl:-10});
  expect(intraday).toMatchObject({quantity:5,average:70,realized:0,pnl:150});
});
test("closed positions retain realized profit with zero open cost", () => {
  const [closed] = ledger([fill("SELL",2,110),fill("BUY",2,100)],[{symbol:"RELIANCE",price:120}]);
  expect(closed).toMatchObject({quantity:0,average:0,realized:20,pnl:0,netValue:0});
});
