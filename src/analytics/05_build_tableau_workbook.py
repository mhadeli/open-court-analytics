"""Phase 3.5: Build a ready-to-open Tableau Packaged Workbook (.twbx).

Packages the privacy-suppressed CSV extracts with a standards-compliant Tableau XML
workbook (`court_dashboard.twb`) containing 4 worksheets and a unified executive
dashboard ready to open directly in Tableau Desktop 2026.3 and publish to Tableau Public.
"""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TABLEAU_DIR = PROJECT_ROOT / "outputs" / "tableau"
TWBX_PATH = TABLEAU_DIR / "court_dashboard.twbx"

TWB_XML = """<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2024.3.0 (20243.24.1010.1014)' source-platform='mac' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <datasources>
    <datasource caption='Maryland County Overall (Suppressed)' inline='true' name='federated.county_overall' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption='court_dashboard_county_overall' name='textscan.county_overall'>
            <connection class='textscan' directory='Data' filename='court_dashboard_county_overall.csv' password='' server='' />
          </named-connection>
        </named-connections>
        <relation connection='textscan.county_overall' name='court_dashboard_county_overall.csv' table='[court_dashboard_county_overall#csv]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>
            <column datatype='string' name='state' ordinal='0' />
            <column datatype='string' name='jurisdiction_fips' ordinal='1' />
            <column datatype='string' name='county_name' ordinal='2' />
            <column datatype='string' name='region' ordinal='3' />
            <column datatype='boolean' name='is_suppressed' ordinal='4' />
            <column datatype='integer' name='total_cases' ordinal='5' />
            <column datatype='real' name='closed_cases' ordinal='6' />
            <column datatype='real' name='evicted_cases' ordinal='7' />
            <column datatype='real' name='clearance_rate_pct' ordinal='8' />
            <column datatype='real' name='eviction_rate_pct' ordinal='9' />
            <column datatype='real' name='batch_efiler_pct' ordinal='10' />
            <column datatype='real' name='median_days_closed' ordinal='11' />
            <column datatype='real' name='pct_disposed_within_30d' ordinal='12' />
            <column datatype='real' name='pct_disposed_within_60d' ordinal='13' />
            <column datatype='real' name='pct_disposed_within_90d' ordinal='14' />
          </columns>
        </relation>
        <metadata-records>
          <metadata-record class='column'>
            <remote-name>state</remote-name>
            <remote-type>129</remote-type>
            <local-name>[state]</local-name>
            <parent-name>[court_dashboard_county_overall.csv]</parent-name>
            <remote-alias>state</remote-alias>
            <ordinal>0</ordinal>
            <local-type>string</local-type>
            <aggregation>Count</aggregation>
            <contains-null>true</contains-null>
          </metadata-record>
          <metadata-record class='column'>
            <remote-name>county_name</remote-name>
            <remote-type>129</remote-type>
            <local-name>[county_name]</local-name>
            <parent-name>[court_dashboard_county_overall.csv]</parent-name>
            <remote-alias>county_name</remote-alias>
            <ordinal>2</ordinal>
            <local-type>string</local-type>
            <aggregation>Count</aggregation>
            <contains-null>true</contains-null>
          </metadata-record>
          <metadata-record class='column'>
            <remote-name>region</remote-name>
            <remote-type>129</remote-type>
            <local-name>[region]</local-name>
            <parent-name>[court_dashboard_county_overall.csv]</parent-name>
            <remote-alias>region</remote-alias>
            <ordinal>3</ordinal>
            <local-type>string</local-type>
            <aggregation>Count</aggregation>
            <contains-null>true</contains-null>
          </metadata-record>
        </metadata-records>
      </connection>
      <column caption='Clearance Rate' datatype='real' default-format='p0.0%' name='[Calc_ClearanceRate]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='SUM([closed_cases]) / SUM([total_cases])' />
      </column>
      <column caption='Eviction Rate' datatype='real' default-format='p0.0%' name='[Calc_EvictionRate]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='SUM([evicted_cases]) / SUM([total_cases])' />
      </column>
      <column caption='County' datatype='string' name='[county_name]' role='dimension' semantic-role='[County].[Name]' type='nominal' />
      <column caption='State' datatype='string' name='[state]' role='dimension' semantic-role='[State].[Name]' type='nominal' />
      <column caption='Region' datatype='string' name='[region]' role='dimension' type='nominal' />
      <column caption='Total Petitions' datatype='integer' default-format='#,##0' name='[total_cases]' role='measure' type='quantitative' />
      <column caption='Closed Cases' datatype='real' default-format='#,##0' name='[closed_cases]' role='measure' type='quantitative' />
      <column caption='Executed Evictions' datatype='real' default-format='#,##0' name='[evicted_cases]' role='measure' type='quantitative' />
      <column caption='Median Days (Closed)' datatype='real' default-format='0.0' name='[median_days_closed]' role='measure' type='quantitative' />
      <column caption='% Disposed &lt;= 60 Days' datatype='real' default-format='0.0' name='[pct_disposed_within_60d]' role='measure' type='quantitative' />
      <column caption='% Disposed &lt;= 90 Days' datatype='real' default-format='0.0' name='[pct_disposed_within_90d]' role='measure' type='quantitative' />
      <column caption='Eviction Rate (%)' datatype='real' default-format='0.0' name='[eviction_rate_pct]' role='measure' type='quantitative' />
      <column caption='Clearance Rate (%)' datatype='real' default-format='0.0' name='[clearance_rate_pct]' role='measure' type='quantitative' />
      <column caption='Batch E-Filer (%)' datatype='real' default-format='0.0' name='[batch_efiler_pct]' role='measure' type='quantitative' />
      <layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />
    </datasource>

    <datasource caption='Maryland Monthly Trends (Suppressed)' inline='true' name='federated.monthly_trends' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption='court_dashboard_monthly' name='textscan.monthly_trends'>
            <connection class='textscan' directory='Data' filename='court_dashboard_monthly.csv' password='' server='' />
          </named-connection>
        </named-connections>
        <relation connection='textscan.monthly_trends' name='court_dashboard_monthly.csv' table='[court_dashboard_monthly#csv]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>
            <column datatype='string' name='state' ordinal='0' />
            <column datatype='string' name='jurisdiction_fips' ordinal='1' />
            <column datatype='string' name='county_name' ordinal='2' />
            <column datatype='string' name='region' ordinal='3' />
            <column datatype='string' name='case_category' ordinal='4' />
            <column datatype='date' name='month_start' ordinal='5' />
            <column datatype='boolean' name='is_suppressed' ordinal='6' />
            <column datatype='real' name='filings_count' ordinal='7' />
            <column datatype='real' name='dispositions_count' ordinal='8' />
            <column datatype='real' name='evictions_count' ordinal='9' />
          </columns>
        </relation>
      </connection>
      <column caption='County' datatype='string' name='[county_name]' role='dimension' semantic-role='[County].[Name]' type='nominal' />
      <column caption='State' datatype='string' name='[state]' role='dimension' semantic-role='[State].[Name]' type='nominal' />
      <column caption='Region' datatype='string' name='[region]' role='dimension' type='nominal' />
      <column caption='Case Category' datatype='string' name='[case_category]' role='dimension' type='nominal' />
      <column caption='Filing Month' datatype='date' name='[month_start]' role='dimension' type='ordinal' />
      <column caption='Filings' datatype='real' default-format='#,##0' name='[filings_count]' role='measure' type='quantitative' />
      <column caption='Dispositions' datatype='real' default-format='#,##0' name='[dispositions_count]' role='measure' type='quantitative' />
      <column caption='Executed Evictions' datatype='real' default-format='#,##0' name='[evictions_count]' role='measure' type='quantitative' />
      <layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />
    </datasource>
  </datasources>

  <worksheets>
    <worksheet name='KPI Summary'>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontcolor='#102a43' fontsize='12'>Statewide Eviction Warrant KPIs (Apr–Sep 2026, Suppressed Public Aggregates)</run>
          </formatted-text>
        </title>
      </layout-options>
      <table>
        <view>
          <datasources>
            <datasource caption='Maryland County Overall (Suppressed)' name='federated.county_overall' />
          </datasources>
          <datasource-dependencies datasource='federated.county_overall'>
            <column caption='Clearance Rate' datatype='real' default-format='p0.0%' name='[Calc_ClearanceRate]' role='measure' type='quantitative'>
              <calculation class='tableau' formula='SUM([closed_cases]) / SUM([total_cases])' />
            </column>
            <column caption='Eviction Rate' datatype='real' default-format='p0.0%' name='[Calc_EvictionRate]' role='measure' type='quantitative'>
              <calculation class='tableau' formula='SUM([evicted_cases]) / SUM([total_cases])' />
            </column>
            <column caption='Total Petitions' datatype='integer' name='[total_cases]' role='measure' type='quantitative' />
            <column caption='Closed Cases' datatype='real' name='[closed_cases]' role='measure' type='quantitative' />
            <column caption='Executed Evictions' datatype='real' name='[evicted_cases]' role='measure' type='quantitative' />
            <column caption='Median Days (Closed)' datatype='real' name='[median_days_closed]' role='measure' type='quantitative' />
            <column-instance column='[total_cases]' derivation='Sum' name='[sum:total_cases:qk]' pivot='key' type='quantitative' />
            <column-instance column='[closed_cases]' derivation='Sum' name='[sum:closed_cases:qk]' pivot='key' type='quantitative' />
            <column-instance column='[evicted_cases]' derivation='Sum' name='[sum:evicted_cases:qk]' pivot='key' type='quantitative' />
            <column-instance column='[Calc_ClearanceRate]' derivation='User' name='[usr:Calc_ClearanceRate:qk]' pivot='key' type='quantitative' />
            <column-instance column='[Calc_EvictionRate]' derivation='User' name='[usr:Calc_EvictionRate:qk]' pivot='key' type='quantitative' />
            <column-instance column='[median_days_closed]' derivation='Median' name='[med:median_days_closed:qk]' pivot='key' type='quantitative' />
          </datasource-dependencies>
          <filter class='categorical' column='[federated.county_overall].[:Measure Names]'>
            <groupfilter function='union' user:op='manual'>
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.county_overall].[sum:total_cases:qk]&quot;' />
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.county_overall].[sum:closed_cases:qk]&quot;' />
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.county_overall].[sum:evicted_cases:qk]&quot;' />
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.county_overall].[usr:Calc_ClearanceRate:qk]&quot;' />
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.county_overall].[usr:Calc_EvictionRate:qk]&quot;' />
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.county_overall].[med:median_days_closed:qk]&quot;' />
            </groupfilter>
          </filter>
          <slices>
            <column>[federated.county_overall].[:Measure Names]</column>
          </slices>
          <aggregation value='true' />
        </view>
        <style>
          <style-rule element='cell'>
            <format attr='font-size' value='16' />
            <format attr='font-weight' value='bold' />
            <format attr='color' value='#1b4965' />
            <format attr='text-align' value='center' />
          </style-rule>
          <style-rule element='label'>
            <format attr='font-size' value='10' />
            <format attr='text-align' value='center' />
          </style-rule>
        </style>
        <panes>
          <pane>
            <view><breakdown value='auto' /></view>
            <mark class='Text' />
            <encodings>
              <text column='[federated.county_overall].[Multiple Values]' />
            </encodings>
          </pane>
        </panes>
        <rows />
        <cols>[federated.county_overall].[:Measure Names]</cols>
      </table>
    </worksheet>

    <worksheet name='Maryland County Map'>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontcolor='#102a43' fontsize='12'>Median Days to Resolution by County (Suppressed &lt;10 Grayed Out)</run>
          </formatted-text>
        </title>
      </layout-options>
      <table>
        <view>
          <datasources>
            <datasource caption='Maryland County Overall (Suppressed)' name='federated.county_overall' />
          </datasources>
          <mapsources>
            <mapsource name='Tableau' />
          </mapsources>
          <datasource-dependencies datasource='federated.county_overall'>
            <column caption='State' datatype='string' name='[state]' role='dimension' semantic-role='[State].[Name]' type='nominal' />
            <column caption='County' datatype='string' name='[county_name]' role='dimension' semantic-role='[County].[Name]' type='nominal' />
            <column caption='Total Petitions' datatype='integer' name='[total_cases]' role='measure' type='quantitative' />
            <column caption='Clearance Rate (%)' datatype='real' name='[clearance_rate_pct]' role='measure' type='quantitative' />
            <column caption='Eviction Rate (%)' datatype='real' name='[eviction_rate_pct]' role='measure' type='quantitative' />
            <column caption='Median Days (Closed)' datatype='real' name='[median_days_closed]' role='measure' type='quantitative' />
            <column-instance column='[state]' derivation='None' name='[none:state:nk]' pivot='key' type='nominal' />
            <column-instance column='[county_name]' derivation='None' name='[none:county_name:nk]' pivot='key' type='nominal' />
            <column-instance column='[median_days_closed]' derivation='Avg' name='[avg:median_days_closed:qk]' pivot='key' type='quantitative' />
            <column-instance column='[total_cases]' derivation='Sum' name='[sum:total_cases:qk]' pivot='key' type='quantitative' />
            <column-instance column='[clearance_rate_pct]' derivation='Avg' name='[avg:clearance_rate_pct:qk]' pivot='key' type='quantitative' />
            <column-instance column='[eviction_rate_pct]' derivation='Avg' name='[avg:eviction_rate_pct:qk]' pivot='key' type='quantitative' />
          </datasource-dependencies>
          <aggregation value='true' />
        </view>
        <style>
          <style-rule element='mark'>
            <encoding attr='color' field='[federated.county_overall].[avg:median_days_closed:qk]' palette='blue_teal_10_0' type='interpolated' />
          </style-rule>
        </style>
        <panes>
          <pane>
            <view><breakdown value='auto' /></view>
            <mark class='Multipolygon' />
            <encodings>
              <lod column='[federated.county_overall].[none:state:nk]' />
              <lod column='[federated.county_overall].[none:county_name:nk]' />
              <color column='[federated.county_overall].[avg:median_days_closed:qk]' />
              <tooltip column='[federated.county_overall].[sum:total_cases:qk]' />
              <tooltip column='[federated.county_overall].[avg:clearance_rate_pct:qk]' />
              <tooltip column='[federated.county_overall].[avg:eviction_rate_pct:qk]' />
            </encodings>
          </pane>
        </panes>
        <rows>[federated.county_overall].[Latitude (generated)]</rows>
        <cols>[federated.county_overall].[Longitude (generated)]</cols>
      </table>
    </worksheet>

    <worksheet name='Monthly Filings vs Dispositions'>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontcolor='#102a43' fontsize='12'>Monthly Warrant Petitions vs. Dispositions (Suppressed Cells &lt;10 Excluded)</run>
          </formatted-text>
        </title>
      </layout-options>
      <table>
        <view>
          <datasources>
            <datasource caption='Maryland Monthly Trends (Suppressed)' name='federated.monthly_trends' />
          </datasources>
          <datasource-dependencies datasource='federated.monthly_trends'>
            <column caption='Filing Month' datatype='date' name='[month_start]' role='dimension' type='ordinal' />
            <column caption='Filings' datatype='real' name='[filings_count]' role='measure' type='quantitative' />
            <column caption='Dispositions' datatype='real' name='[dispositions_count]' role='measure' type='quantitative' />
            <column caption='Executed Evictions' datatype='real' name='[evictions_count]' role='measure' type='quantitative' />
            <column-instance column='[month_start]' derivation='Month-Trunc' name='[tmn:month_start:qk]' pivot='key' type='quantitative' />
            <column-instance column='[filings_count]' derivation='Sum' name='[sum:filings_count:qk]' pivot='key' type='quantitative' />
            <column-instance column='[dispositions_count]' derivation='Sum' name='[sum:dispositions_count:qk]' pivot='key' type='quantitative' />
            <column-instance column='[evictions_count]' derivation='Sum' name='[sum:evictions_count:qk]' pivot='key' type='quantitative' />
          </datasource-dependencies>
          <filter class='categorical' column='[federated.monthly_trends].[:Measure Names]'>
            <groupfilter function='union' user:op='manual'>
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.monthly_trends].[sum:filings_count:qk]&quot;' />
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.monthly_trends].[sum:dispositions_count:qk]&quot;' />
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.monthly_trends].[sum:evictions_count:qk]&quot;' />
            </groupfilter>
          </filter>
          <slices>
            <column>[federated.monthly_trends].[:Measure Names]</column>
          </slices>
          <aggregation value='true' />
        </view>
        <style />
        <panes>
          <pane>
            <view><breakdown value='auto' /></view>
            <mark class='Line' />
            <encodings>
              <color column='[federated.monthly_trends].[:Measure Names]' />
            </encodings>
          </pane>
        </panes>
        <rows>[federated.monthly_trends].[Multiple Values]</rows>
        <cols>[federated.monthly_trends].[tmn:month_start:qk]</cols>
      </table>
    </worksheet>

    <worksheet name='Time-Standard Compliance (60d)'>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontcolor='#102a43' fontsize='12'>% of Closed Petitions Disposed Within 60 Days by Jurisdiction</run>
          </formatted-text>
        </title>
      </layout-options>
      <table>
        <view>
          <datasources>
            <datasource caption='Maryland County Overall (Suppressed)' name='federated.county_overall' />
          </datasources>
          <datasource-dependencies datasource='federated.county_overall'>
            <column caption='County' datatype='string' name='[county_name]' role='dimension' semantic-role='[County].[Name]' type='nominal' />
            <column caption='Region' datatype='string' name='[region]' role='dimension' type='nominal' />
            <column caption='% Disposed &lt;= 60 Days' datatype='real' name='[pct_disposed_within_60d]' role='measure' type='quantitative' />
            <column-instance column='[county_name]' derivation='None' name='[none:county_name:nk]' pivot='key' type='nominal' />
            <column-instance column='[region]' derivation='None' name='[none:region:nk]' pivot='key' type='nominal' />
            <column-instance column='[pct_disposed_within_60d]' derivation='Avg' name='[avg:pct_disposed_within_60d:qk]' pivot='key' type='quantitative' />
          </datasource-dependencies>
          <computed-sort column='[federated.county_overall].[none:county_name:nk]' direction='DESC' using='[federated.county_overall].[avg:pct_disposed_within_60d:qk]' />
          <aggregation value='true' />
        </view>
        <style />
        <panes>
          <pane>
            <view><breakdown value='auto' /></view>
            <mark class='Bar' />
            <encodings>
              <color column='[federated.county_overall].[none:region:nk]' />
            </encodings>
          </pane>
        </panes>
        <rows>[federated.county_overall].[none:county_name:nk]</rows>
        <cols>[federated.county_overall].[avg:pct_disposed_within_60d:qk]</cols>
      </table>
    </worksheet>
  </worksheets>

  <dashboards>
    <dashboard name='Maryland Court Analytics'>
      <style />
      <size maxheight='960' maxwidth='1400' minheight='960' minwidth='1400' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
          <zone h='98000' id='2' param='vert' type-v2='layout-flow' w='98400' x='800' y='1000'>
            <zone fixed-size='56' h='6000' id='3' is-fixed='true' type-v2='text' w='98400' x='800' y='1000'>
              <formatted-text>
                <run bold='true' fontcolor='#102a43' fontsize='18'>Maryland District Court Eviction Warrant Analytics (Open Court Analytics)</run>
                <run>&#10;</run>
                <run fontcolor='#486581' fontsize='10'>NODS-aligned public aggregates (Apr–Sep 2026) | Small-cell privacy suppression (&lt;10 cases) enforced upstream in SQL</run>
              </formatted-text>
            </zone>
            <zone fixed-size='115' h='12000' id='4' is-fixed='true' name='KPI Summary' w='98400' x='800' y='7000' />
            <zone h='44000' id='5' param='horz' type-v2='layout-flow' w='98400' x='800' y='19000'>
              <zone h='44000' id='6' name='Maryland County Map' w='51000' x='800' y='19000' />
              <zone h='44000' id='7' name='Monthly Filings vs Dispositions' w='47400' x='51800' y='19000' />
            </zone>
            <zone h='31000' id='8' name='Time-Standard Compliance (60d)' w='98400' x='800' y='63000' />
            <zone fixed-size='44' h='5000' id='9' is-fixed='true' type-v2='text' w='98400' x='800' y='94000'>
              <formatted-text>
                <run fontcolor='#627d98' fontsize='8'>Source: District Court of Maryland Eviction Case Data (opendata.maryland.gov, mvqb-b4hf). Zero case-level rows or PII exported; cells &lt;10 suppressed (e.g., Garrett County median). Closed-case medians reflect resolved petitions only (see analytical brief for Kaplan–Meier right-censored 65d median). Descriptive operational metrics only — not causal.</run>
              </formatted-text>
            </zone>
          </zone>
        </zone>
      </zones>
    </dashboard>
  </dashboards>
</workbook>
"""


def main() -> None:
    # Validate well-formed XML before packaging
    ET.fromstring(TWB_XML.encode("utf-8"))

    csv_files = [
        TABLEAU_DIR / "court_dashboard_county_overall.csv",
        TABLEAU_DIR / "court_dashboard_monthly.csv",
        TABLEAU_DIR / "court_dashboard_county_category.csv",
    ]
    for f in csv_files:
        if not f.exists():
            raise FileNotFoundError(f"Missing CSV extract: {f}. Run 04_export_tableau.py first.")

    with zipfile.ZipFile(TWBX_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("court_dashboard.twb", TWB_XML.encode("utf-8"))
        for f in csv_files:
            zf.write(f, arcname=f"Data/{f.name}")

    print(f"[ok] Built valid Tableau Packaged Workbook -> {TWBX_PATH} ({TWBX_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
