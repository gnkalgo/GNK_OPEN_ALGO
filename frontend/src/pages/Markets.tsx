import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowUpRight, Plus, Search, Star } from "lucide-react";
import { instruments, money, paper } from "../api/paper";
import { useAction, usePaper } from "../hooks";
import {
  Badge,
  Change,
  Chart,
  Empty,
  Feedback,
  PageHead,
  Panel,
} from "../components/ui";
export default function Markets() {
  const a = useAction();
  const [query, setQuery] = useState(""),
    [tab, setTab] = useState("All instruments"),
    [period, setPeriod] = useState("1D");
  const [params, setParams] = useSearchParams(),
    { watchlist, scenario } = usePaper();
  const selected =
    instruments.find((i) => i.symbol === params.get("symbol")) ??
    instruments[0];
  const list =
    scenario === "empty"
      ? []
      : instruments.filter(
          (i) =>
            `${i.symbol} ${i.name}`
              .toLowerCase()
              .includes(query.toLowerCase()) &&
            (tab !== "Watchlist" || watchlist.includes(i.symbol)),
        );
  return (
    <>
      <PageHead
        eyebrow="FIND YOUR NEXT OPPORTUNITY"
        title="Markets"
        subtitle="Your instruments, your watchlist, your perspective."
      >
        <Badge tone={scenario === "feed-offline" ? "amber" : "green"}>
          {scenario === "feed-offline"
            ? "Feed disconnected · stale"
            : "Simulated feed connected"}
        </Badge>
      </PageHead>
      <Feedback {...a} />
      <div className="market-layout">
        <Panel
          title="Market explorer"
          extra={
            <span className="muted text-xs">Fictional NSE / BSE data</span>
          }
        >
          <div className="market-controls">
            <div className="search-field">
              <Search size={16} />
              <input
                aria-label="Search symbols"
                placeholder="Search symbols or company names…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div className="tabs">
              {["All instruments", "Watchlist"].map((t) => (
                <button
                  className={t === tab ? "active" : ""}
                  onClick={() => setTab(t)}
                  key={t}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          {list.length === 0 ? (
            <Empty
              title="No instruments found"
              detail="Try another symbol or add an instrument to your watchlist."
            />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>WATCH</th>
                    <th>INSTRUMENT</th>
                    <th>LAST PRICE</th>
                    <th>CHANGE</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {list.map((i) => (
                    <tr
                      key={i.symbol}
                      className={
                        selected.symbol === i.symbol ? "selected-row" : ""
                      }
                    >
                      <td>
                        <button
                          className={`icon-btn ${watchlist.includes(i.symbol) ? "starred" : ""}`}
                          aria-label={`${watchlist.includes(i.symbol) ? "Remove" : "Add"} ${i.symbol} ${watchlist.includes(i.symbol) ? "from" : "to"} watchlist`}
                          onClick={() =>
                            void a.run(async () => {
                              await paper.toggleWatch(i.symbol);
                            })
                          }
                        >
                          <Star
                            size={15}
                            fill={
                              watchlist.includes(i.symbol)
                                ? "currentColor"
                                : "none"
                            }
                          />
                        </button>
                      </td>
                      <td>
                        <button
                          className="symbol-button"
                          onClick={() => setParams({ symbol: i.symbol })}
                        >
                          <b>{i.symbol}</b>
                          <small>
                            {i.name} · {i.exchange}
                          </small>
                        </button>
                      </td>
                      <td>{money(i.price)}</td>
                      <td>
                        <Change value={i.change} />
                      </td>
                      <td>
                        <Link
                          className="icon-btn"
                          aria-label={`Trade ${i.symbol}`}
                          to={`/app/orders/new?symbol=${i.symbol}`}
                        >
                          <ArrowUpRight size={16} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
        <Panel
          title={selected.symbol}
          extra={<Badge>{selected.exchange}</Badge>}
        >
          <div className="instrument-detail">
            <p>{selected.name}</p>
            <strong>{money(selected.price)}</strong>
            <Change value={selected.change} />
            <div className="segmented">
              {["1D", "1W", "1M"].map((p) => (
                <button
                  onClick={() => setPeriod(p)}
                  className={p === period ? "selected" : ""}
                  key={p}
                >
                  {p}
                </button>
              ))}
            </div>
            <Chart period={period} />
            <small className="muted">
              Illustrative chart · Not live market data
            </small>
            <dl className="detail-grid">
              <div>
                <dt>Open</dt>
                <dd>{money(selected.price - 12)}</dd>
              </div>
              <div>
                <dt>Previous close</dt>
                <dd>{money(selected.price - 8)}</dd>
              </div>
              <div>
                <dt>Day high</dt>
                <dd>{money(selected.price + 20)}</dd>
              </div>
              <div>
                <dt>Day low</dt>
                <dd>{money(selected.price - 25)}</dd>
              </div>
            </dl>
            <Link
              className={`button primary full ${scenario === "feed-offline" ? "disabled" : ""}`}
              aria-disabled={scenario === "feed-offline"}
              onClick={(e) => {
                if (scenario === "feed-offline") e.preventDefault();
              }}
              to={`/app/orders/new?symbol=${selected.symbol}`}
            >
              <Plus size={16} /> Create paper order
            </Link>
          </div>
        </Panel>
      </div>
    </>
  );
}
