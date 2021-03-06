import React, { Component} from 'react';
import shouldPureComponentUpdate from 'react-pure-render/function';

import {markerStyle, markerStyleHover} from './hover_styles.js';

export default class Marker extends Component {
//   static propTypes = {
//     // GoogleMap pass $hover props to hovered components
//     // to detect hover it uses internal mechanism, explained in x_distance_hover example
//     $hover: PropTypes.bool,
//     text: PropTypes.string
//   };

  static defaultProps = {
      $hover: false,
      text: "N/A",
      event: null
  };

  shouldComponentUpdate = shouldPureComponentUpdate;

  constructor(props) {
    super(props);

    this.state = {
      event: props.data
    }

    this.showEvent = this.showEvent.bind(this)
  }

  showEvent() {
    this.props.eventFunc(this.state.event, this);
  }

  render() {
    const style = this.props.$hover ? markerStyleHover : markerStyle;

    return (
       <div style={style} onClick={this.showEvent}>
          {this.state.event.votes}
       </div>
    );
  }
}