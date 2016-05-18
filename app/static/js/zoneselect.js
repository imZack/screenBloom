var zoneGrid = {
    'width'         : 16,
    'height'        : 9,
    'colors'        : ['green', 'blue', 'black', 'yellow', 'cyan', 'pink', 'red', 'orange'],
    'defaultColor'  : 'grey',
    'zones'         : [],
    'lights'        : [],
    'state'         : true
};

zoneGrid.init = function() {
    console.log('startin this bitch off right');
    startGrid();

    $('#restart').on('click', function() {
        if (confirm('Are you sure, you want to delete all zones?')) {
            zoneGrid.zones = [];
            startGrid();
        }
    });

    $('#save_zones').on('click', function() {
        saveResults();
    });
};

//build the grid, and place click event
function startGrid() {
    var grid = $('#grid');
    grid.html(''); //clear grid
    updateComboForm();//clear result

    for (var line_index=0; line_index<zoneGrid.height; line_index++) {
        //build each line
        var line_id = "line_" + line_index;
        grid.append("<div class='line' id='" + line_id + "' ></div>");
        for (var row_index=0; row_index<zoneGrid.width; row_index++) {
            //build each column
            var line = $('#' + line_id),
                row_id = "row_" + line_index + "_" + row_index;
            line.append("<div class='row' id='" + row_id + "' >&nbsp;</div>");
            var row = $('#' + row_id);

            //default color
            row.css('background-color', zoneGrid.defaultColor);
            //restore colour if zone is got from config
            $.each(zoneGrid.zones, function(zone_index, zone) {
                if (line_index >= zone.y1 && line_index <= zone.y2 && row_index >= zone.x1 && row_index <= zone.x2) {
                    row.css('background-color', zoneGrid.colors[zone_index]);
                }
            });
            //place event
            row.on('click', cellClick);
            row.on('mouseover', cellOver);
        }
    }
}

//get the top left and bottom right corners from two cell
function getCorners(cellA, cellB) {
    return {
        'x1': Math.min(cellA.attr('id').split('_')[2], cellB.attr('id').split('_')[2]),
        'y1': Math.min(cellA.attr('id').split('_')[1], cellB.attr('id').split('_')[1]),
        'x2': Math.max(cellA.attr('id').split('_')[2], cellB.attr('id').split('_')[2]),
        'y2': Math.max(cellA.attr('id').split('_')[1], cellB.attr('id').split('_')[1])
    };
}

//preview mode
function cellOver() {
    console.log('we mousin\' now');
    if (selectionStarted) {
        var cur_cell = $(this),
            corners = getCorners(startCell, cur_cell);
        clearPixels();
        selectZone(corners, false); //just preview
    }
}

//on click, for start or stop selection
var selectionStarted = false,
    startCell, endCell;

function cellClick() {
    console.log('O shit waddup');
    var cur_cell = $(this);
    //first click to start selection
    if (!selectionStarted) {
        startCell = cur_cell;
        markCell(cur_cell, true);
        selectionStarted = true;
    } else {
        //second click to end selection
        endCell = cur_cell;
        selectionStarted = false;
        var corners = getCorners(startCell, endCell);
        validateZone(corners);
    }
}

//clear unselected pixels
function clearPixels() {
    for (var line_index=0; line_index<zoneGrid.height; line_index++) {
        for (var row_index=0; row_index<zoneGrid.width; row_index++) {
            //restoring default color
            var cur_cell = $('#row_' + line_index + "_" + row_index);
            if (!cur_cell.hasClass('selected')) {
                cur_cell.css('background-color', zoneGrid.defaultColor);
            } else {
                //restoring zone zone_colors
                $.each(zoneGrid.zones, function(zone_index, zone) {
                    console.log(zone_index);
                    if (line_index >= zone.y1 && line_index <= zone.y2 && row_index >= zone.x1 && row_index <= zone.x2) {
                        console.log(zoneGrid.colors[zone_index]);
                        console.log(cur_cell);
                        cur_cell.css('background-color', zoneGrid.colors[zone_index]);
                    }
                });
            }
        }
    }
}

function markCell(cell, validate) {
    if (validate == true) {
        cell.addClass('selected');
    }
    cell.css('background-color', zoneGrid.colors[zoneGrid.zones.length]);
}

//change the color of cells, and add class 'selected' if validate is true
function selectZone(corners, validate) {
    for (var line_index=corners.y1; line_index<=corners.y2; line_index++) {
        for (var row_index=corners.x1; row_index<= corners.x2; row_index++) {
            var cell_id = "row_" + line_index + "_" + row_index,
                cell = $('#' + cell_id);
            markCell(cell, validate);
        }
    }
}

function selectZoneBulb(zoneIndex) {
    var select = $("#select_" + zoneIndex);
    zoneGrid.zones[zoneIndex].bulb = select.val();
    updateComboForm();
}

function updateComboForm() {
    //builds the form for bulb selection
    $('#combo').html('');
    $.each(zoneGrid.zones, function(zone_index) {
        var html = "<label for='select_" + zone_index + "'>Zone " + zoneGrid.colors[zone_index] + ": </label><select id='select_" + zone_index + "' onchange='selectZoneBulb(" + zone_index + ")'>";
        $.each(zoneGrid.lights, function(index_light, name) {
            var selected = '';
            if (zoneGrid.zones[zone_index] && zoneGrid.zones[zone_index].bulb && zoneGrid.zones[zone_index].bulb === index_light) {
                selected = " selected='selected' ";
            }
            html += "<option value='" + index_light + "' " + selected + ">" + name + "</option>";
        });
        html += "</select><br/>";

        $('#combo').append(html);
        $("#select_" + zone_index).on('change', function() {
            selectZoneBulb(zone_index);
        });
    });
}

function validateZone(corners) {
    //here you have the 2 point for the zone selection
    //so you could save that value for the calc matrix
    selectZone(corners, true); //update color and mark as selected
    corners.bulb = Object.keys(zoneGrid.lights)[0]; //add a default bulb
    zoneGrid.zones.push(corners); //add the zone in result
    updateComboForm();
}

function saveResults(){
    console.log('Saving Zones');
    //verify if no bulb is used twice
    var used_bulbs = {},
        found = false;

    zoneGrid.zones.forEach(function(zone){
        if (typeof(used_bulbs[zone.bulb] !== 'undefined')){
            found = true;
        } else{
            used_bulbs[zone.bulb] = true;
        }
    });

    if (found) {
        alert("Each bulb must be assign to only one zone");
        return false;
    } else{
        $.ajax({
            url			: $SCRIPT_ROOT + '/update-zones',
            method		: 'POST',
            contentType	: 'application/json;charset=UTF-8',
            data		: JSON.stringify(zoneGrid.zones),
            success: function (result) {
                console.log(result)
            },
            error: function (result) {
                console.log(result);
            }
        });
    }
}

function toggleZone() {
    var oldZones = zoneGrid.zones.slice(0);
    zoneGrid.zones = [];
    if (zoneGrid.state === true) {
        console.log('disactivating multiple zones');
        zoneGrid.state = false;
        $("#zone_state").html("Off");
        $('#zone_select').hide();
    } else {
        console.log('activating multiple zones');
        zoneGrid.state = true;
        $("#zone_state").html("On");
        $('#zone_select').show();
        if (oldZones) {
            zoneGrid.zones = oldZones;
        }
    }
    $('#zone_btn .setting-circle').removeClass('setting-clicked');
    saveResults();
}