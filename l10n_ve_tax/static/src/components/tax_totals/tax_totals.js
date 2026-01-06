/** @odoo-module **/

import { formatFloat, formatMonetary } from "@web/views/fields/formatters";
import { parseFloat } from "@web/views/fields/parsers";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";

import { TaxTotalsComponent } from "@account/components/tax_totals/tax_totals";

const { Component, onPatched, onWillUpdateProps, useRef, toRaw, useState } = owl;


export class TaxTotalsComponents extends TaxTotalsComponent {
  get currencyId() {
    return this.props.record.data.foreign_currency_id;
  }

  formatData(props) {
////////////////////////////////
// Verificar si hay datos disponibles
    if (!props.record.data || !props.record.data[this.props.name]) {
        console.warn("No data available for the specified name:", this.props.name);
        return;
    }
 /////////////////////////////////
    
    let totals = JSON.parse(JSON.stringify(toRaw(props.record.data[this.props.name])));
    console.log("Datos de entrada:", props.record.data[this.props.name]);    //verifica la estructura de datos
//   if (!totals) {
 //     return;
 //   }
/////////////////////////////////////
     // Verificar si totals es un objeto
    if (typeof totals !== 'object' || totals === null) {
        console.error("Invalid totals data:", totals);
        return;
    }
/////////////////////////////////////////////
    
    // Verificar si totals está definido
    if (!totals) {
      console.warn("No totals data available");
      return;
    }

    // Verificar si subtotals_order es un array
    if (!Array.isArray(totals.subtotals_order)) {
      console.error("totals.subtotals_order is not iterable", totals);
      totals.subtotals_order = []; // O asignar un valor por defecto      
//return; // Salir si no es iterable
    }

 // Asegurarse de que groups_by_subtotal sea un objeto
    if (typeof totals.groups_by_subtotal !== 'object' || totals.groups_by_subtotal === null) {
        console.error("totals.groups_by_subtotal is not an object", totals);
        totals.groups_by_subtotal = {}; // Inicializar como un objeto vacío
    }
// Asegurarse de que subtotals sea un array
    totals.subtotals = totals.subtotals || []; // Inicializar como un array vacío si no está definido

    const currencyFmtOpts = { currencyId: props.record.data.currency_id && props.record.data.currency_id[0] };

    let amount_untaxed = totals.amount_untaxed || 0; // Asegurarse de que amount_untaxed tenga un valor
    let amount_tax = 0;
    let subtotals = [];
    for (let subtotal_title of totals.subtotals_order) {
      let amount_total = amount_untaxed + amount_tax;
      subtotals.push({
        'name': subtotal_title,
        'amount': amount_total,
        'formatted_amount': formatMonetary(amount_total, currencyFmtOpts),
      });
      let group = totals.groups_by_subtotal[subtotal_title] || []; // Asegurarse de que group sea un array
      for (let i in group) {
        amount_tax = amount_tax + group[i].tax_group_amount || 0; // Asegurarse de que tax_group_amount tenga un valor
      }
    }
    totals.subtotals = subtotals;
    let rounding_amount = totals.display_rounding && totals.rounding_amount || 0;
    let amount_total = amount_untaxed + amount_tax + rounding_amount;
    totals.amount_total = amount_total;
    totals.formatted_amount_total = formatMonetary(amount_total, currencyFmtOpts);
    for (let group_name of Object.keys(totals.groups_by_subtotal)) {
      let group = totals.groups_by_subtotal[group_name] || []; // Asegurarse de que group sea un array
      for (let key in group) {
        group[key].formatted_tax_group_amount = formatMonetary(group[key].tax_group_amount, currencyFmtOpts);
        group[key].formatted_tax_group_base_amount = formatMonetary(group[key].tax_group_base_amount, currencyFmtOpts);
      }
    }
    this.totals = totals;
  }
}
TaxTotalsComponents.template = "l10n_ve_tax.TaxForeignTotalsField";
TaxTotalsComponents.props = {
  ...standardFieldProps,
};

export const taxTotalsComponent = {
  component: TaxTotalsComponents,
};

registry.category("fields").add("account-tax-foreign-totals-field", taxTotalsComponent);
